# app/endpoints.py
# API endpoint handlers

import os
import time
import logging
import tempfile
import traceback
import asyncio
from datetime import datetime, timedelta

from fastapi import HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import (
    get_db, User, ResumeJob, UserResumeTemplate, SessionLocal,
    generate_cache_key, get_cached_job_search, store_job_search_cache,
    get_job_description, store_job_posting, cleanup_expired_cache, get_cache_stats,
    JobSearchCache
)
from app.auth import get_current_user
from app.create_resume import create_resume
from app.job_processing import process_resume_parallel, job_progress
from app.job_scraper import job_scraper

logger = logging.getLogger(__name__)


def validate_resume_payload(data: dict) -> list:
    """
    Validate the resume generation payload.
    Returns a list of error messages (empty if valid).
    """
    errors = []
    
    mode = data.get("mode", "complete_jd")
    job_data = data.get("job_description_data", {})
    resume_data = data.get("resume_data", {})
    
    # Validate Job Description (required for all modes)
    jd_text = job_data.get("job_description", "").strip()
    if not jd_text or len(jd_text) < 50:
        errors.append("Job Description must be at least 50 characters")
    
    company_name = job_data.get("company_name", "").strip()
    if not company_name:
        errors.append("Company Name is required")
    
    job_title = job_data.get("job_title", "").strip()
    if not job_title:
        errors.append("Job Title is required")
    
    # Validate Resume Data (only for resume+jd mode)
    if mode == "resume_jd":
        name = resume_data.get("name", "").strip()
        if not name:
            errors.append("Name is required in Resume+JD mode")
        
        summary = resume_data.get("summary", "").strip()
        if not summary or len(summary) < 50:
            errors.append("Professional Summary must be at least 50 characters")
        
        # Check contact
        contact = resume_data.get("contact", {})
        if isinstance(contact, dict):
            if not contact.get("email") and not contact.get("phone"):
                errors.append("At least one contact method (Email or Phone) is required")
        
        # Check technical skills
        skills = resume_data.get("technical_skills", {})
        if not skills or not isinstance(skills, dict):
            errors.append("Technical Skills are required")
        else:
            has_skills = any(
                isinstance(v, list) and len(v) > 0 
                for v in skills.values()
            )
            if not has_skills:
                errors.append("Technical Skills must have at least one skill listed")
        
        # Check experience
        experience = resume_data.get("experience", [])
        if not experience or not isinstance(experience, list) or len(experience) == 0:
            errors.append("At least one Experience entry is required")
        else:
            for idx, exp in enumerate(experience):
                if not exp.get("company"):
                    errors.append(f"Experience {idx + 1}: Company name is required")
                if not (exp.get("role") or exp.get("title") or exp.get("job_title")):
                    errors.append(f"Experience {idx + 1}: Job title is required")
                bullets = exp.get("bullets", exp.get("points", exp.get("responsibilities", [])))
                if not bullets or len(bullets) == 0:
                    errors.append(f"Experience {idx + 1}: At least one responsibility is required")
        
        # Check education
        education = resume_data.get("education", [])
        if not education or not isinstance(education, list) or len(education) == 0:
            errors.append("At least one Education entry is required")
        else:
            for idx, edu in enumerate(education):
                if not edu.get("degree"):
                    errors.append(f"Education {idx + 1}: Degree is required")
                if not edu.get("institution"):
                    errors.append(f"Education {idx + 1}: Institution is required")
    
    return errors


def process_resume_background(data: dict, request_id: str, job_id: int):
    """Background task to process resume"""
    db = SessionLocal()
    try:
        job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
        if job:
            job.status = "processing"
            user = db.query(User).filter(User.user_id == job.user_id).first()
            if user:
                user.active_jobs_count = (user.active_jobs_count or 0) + 1
            db.commit()
        
        result = asyncio.run(process_resume_parallel(data, request_id, db))
        
        if job:
            job.final_resume_json = result
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            user = db.query(User).filter(User.user_id == job.user_id).first()
            if user:
                user.total_resumes_generated = (user.total_resumes_generated or 0) + 1
                user.active_jobs_count = max(0, (user.active_jobs_count or 1) - 1)
            db.commit()
        logger.info(f"Resume generation completed for job {job_id}")
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")
        job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            user = db.query(User).filter(User.user_id == job.user_id).first()
            if user:
                user.active_jobs_count = max(0, (user.active_jobs_count or 1) - 1)
            db.commit()
    finally:
        db.close()


async def generate_resume_json(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate resume with job tracking"""
    try:
        MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
        active_jobs = db.query(ResumeJob).filter(
            ResumeJob.user_id == current_user.user_id,
            ResumeJob.status.in_(["pending", "processing"])
        ).count()
        if active_jobs >= MAX_CONCURRENT_JOBS:
            raise HTTPException(status_code=429, detail=f"Too many concurrent jobs")
        data = await request.json()
        
        # Validate input payload
        validation_errors = validate_resume_payload(data)
        if validation_errors:
            raise HTTPException(status_code=400, detail=f"Validation failed: {'; '.join(validation_errors)}")
        
        request_id = data.get("request_id", f"req_{int(time.time())}_{current_user.user_id}")
        
        # Extract job description data (support both formats)
        job_data = data.get("job_description_data", {})
        company_name = job_data.get("company_name") or data.get("company_name", "Unknown")
        job_title = job_data.get("job_title") or data.get("job_title", "Unknown")
        jd_text = job_data.get("job_description") or data.get("jd", "")
        
        resume_job = ResumeJob(
            user_id=current_user.user_id,
            request_id=request_id,
            company_name=company_name,
            job_title=job_title,
            mode=data.get("mode", "complete_jd"),
            jd_text=jd_text,
            resume_input_json=data.get("resume_data", {}),
            status="pending",
            progress=0
        )
        db.add(resume_job)
        db.commit()
        db.refresh(resume_job)
        background_tasks.add_task(process_resume_background, data, request_id, resume_job.id)
        return {"message": "Resume generation started", "request_id": request_id, "job_id": resume_job.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_job_status(request_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id, ResumeJob.user_id == current_user.user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    memory_progress = job_progress.get(request_id, {})
    return {"job_id": job.id, "request_id": job.request_id, "status": job.status, "progress": memory_progress.get("progress", job.progress), "message": memory_progress.get("message", ""), "company_name": job.company_name, "job_title": job.job_title, "created_at": job.created_at.isoformat(), "completed_at": job.completed_at.isoformat() if job.completed_at else None, "error_message": job.error_message}


async def get_job_result(request_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id, ResumeJob.user_id == current_user.user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed")
    return {"job_id": job.id, "request_id": job.request_id, "company_name": job.company_name, "job_title": job.job_title, "final_resume": job.final_resume_json, "completed_at": job.completed_at.isoformat()}


async def update_job_resume(request_id: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id, ResumeJob.user_id == current_user.user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed, cannot update")
    
    try:
        body = await request.json()
        updated_resume = body.get("final_resume")
        
        if not updated_resume:
            raise HTTPException(status_code=400, detail="No resume data provided")
        
        # Update the resume JSON in the database
        job.final_resume_json = updated_resume
        db.commit()
        
        return {"success": True, "message": "Resume updated successfully", "request_id": request_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update resume: {str(e)}")


async def download_resume(request_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id, ResumeJob.user_id == current_user.user_id).first()
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="Completed job not found")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
            tmp_path = tmp_file.name
        create_resume(job.final_resume_json, tmp_path)
        with open(tmp_path, 'rb') as f:
            docx_content = f.read()
        os.unlink(tmp_path)
        filename = f"{job.company_name}_{job.job_title}_Resume.docx".replace(" ", "_").replace("/", "_")
        return Response(content=docx_content, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def download_job_description(request_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id, ResumeJob.user_id == current_user.user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        filename = f"{job.company_name}_{job.job_title}_JD.txt".replace(" ", "_").replace("/", "_")
        return Response(content=job.jd_text, media_type='text/plain', headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_user_jobs(
    limit: int = 20, 
    offset: int = 0, 
    company: str = None,
    job_title: str = None,
    status: str = None,
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # Base query
    query = db.query(ResumeJob).filter(ResumeJob.user_id == current_user.user_id)
    
    # Apply filters
    if company:
        query = query.filter(ResumeJob.company_name.ilike(f"%{company}%"))
    if job_title:
        query = query.filter(ResumeJob.job_title.ilike(f"%{job_title}%"))
    if status:
        query = query.filter(ResumeJob.status == status)
    
    # Get total count with filters applied
    total_count = query.count()
    
    # Get paginated jobs
    jobs = query.order_by(ResumeJob.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "count": total_count,
        "jobs": [
            {
                "job_id": job.id,
                "request_id": job.request_id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "mode": job.mode,
                "status": job.status,
                "progress": job.progress,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            } for job in jobs
        ]
    }


async def get_user_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_resumes = db.query(ResumeJob).filter(ResumeJob.user_id == current_user.user_id, ResumeJob.created_at >= today_start, ResumeJob.status == "completed").count()
    active_jobs = db.query(ResumeJob).filter(ResumeJob.user_id == current_user.user_id, ResumeJob.status.in_(["pending", "processing"])).count()
    max_concurrent = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
    return {"user_id": user.user_id, "total_resumes": user.total_resumes_generated or 0, "today_resumes": today_resumes, "active_jobs": active_jobs, "limits": {"max_concurrent_jobs": max_concurrent, "rate_limit": "5 requests per minute"}, "remaining": {"concurrent_slots": max(0, max_concurrent - active_jobs)}, "account_created": user.created_at.isoformat(), "last_login": user.last_login.isoformat() if user.last_login else None}


async def save_resume_template(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        data = await request.json()
        resume_data = data.get("resume_data", data)
        template = db.query(UserResumeTemplate).filter(UserResumeTemplate.user_id == current_user.user_id).first()
        if template:
            template.resume_data = resume_data
            template.updated_at = datetime.utcnow()
        else:
            template = UserResumeTemplate(user_id=current_user.user_id, resume_data=resume_data)
            db.add(template)
        db.commit()
        db.refresh(template)
        return {"message": "Resume template saved successfully", "updated_at": template.updated_at.isoformat()}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def get_resume_template(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    template = db.query(UserResumeTemplate).filter(UserResumeTemplate.user_id == current_user.user_id).first()
    if not template:
        return {"has_template": False, "resume_data": None}
    resume_data = template.resume_data
    if isinstance(resume_data, dict) and "resume_data" in resume_data:
        resume_data = resume_data["resume_data"]
    return {"has_template": True, "resume_data": resume_data, "updated_at": template.updated_at.isoformat()}


async def delete_job(request_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a resume job and its associated files"""
    try:
        # Find the job
        job = db.query(ResumeJob).filter(
            ResumeJob.request_id == request_id,
            ResumeJob.user_id == current_user.user_id
        ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Delete associated files if they exist
        import os
        generated_resumes_dir = "generated_resumes"
        
        # Delete resume file
        resume_filename = f"{job.company_name}_{job.job_title}_Resume.docx"
        resume_path = os.path.join(generated_resumes_dir, resume_filename)
        if os.path.exists(resume_path):
            os.remove(resume_path)
        
        # Delete job description file if it exists
        jd_filename = f"{job.company_name}_{job.job_title}_JD.txt"
        jd_path = os.path.join(generated_resumes_dir, jd_filename)
        if os.path.exists(jd_path):
            os.remove(jd_path)
        
        # Delete from database
        db.delete(job)
        db.commit()
        
        return {"message": "Job deleted successfully", "request_id": request_id}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")


def cleanup_stale_jobs(db: Session):
    """Clean up jobs that have been stuck in processing for too long"""
    try:
        from datetime import datetime, timedelta
        
        # Find jobs stuck in processing/pending for more than 10 minutes
        stale_threshold = datetime.utcnow() - timedelta(minutes=10)
        
        stale_jobs = db.query(ResumeJob).filter(
            ResumeJob.status.in_(["pending", "processing"]),
            ResumeJob.created_at < stale_threshold
        ).all()
        
        if stale_jobs:
            logger.info(f"[CLEANUP] Found {len(stale_jobs)} stale jobs")
            
            for job in stale_jobs:
                logger.info(f"[CLEANUP] Marking job {job.request_id} as failed (stuck since {job.created_at})")
                job.status = "failed"
                job.error_message = "Job timed out - exceeded maximum processing time"
                
                # Decrement active job count for user
                user = db.query(User).filter(User.user_id == job.user_id).first()
                if user and user.active_jobs_count and user.active_jobs_count > 0:
                    user.active_jobs_count = max(0, user.active_jobs_count - 1)
            
            db.commit()
            logger.info(f"[CLEANUP] Cleaned up {len(stale_jobs)} stale jobs")
        
    except Exception as e:
        logger.error(f"[CLEANUP] Error during cleanup: {str(e)}")
        db.rollback()


async def parse_resume_document(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Parse uploaded resume document (PDF/DOCX) and convert to JSON.
    Extracts text from document and uses LLM to structure it.
    """
    from app.document_parser import extract_text_from_document
    from app.utils import parse_resume_text_to_json
    
    try:
        # Parse multipart form data
        form = await request.form()
        
        # Get the uploaded file
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")
        
        # Read file content
        file_content = await file.read()
        filename = file.filename or "resume.pdf"
        
        logger.info(f"[PARSE_RESUME] User {current_user.user_id} uploading: {filename} ({len(file_content)} bytes)")
        
        # Validate file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
        
        # Extract text from document
        try:
            extracted_text = extract_text_from_document(file_content, filename)
            logger.info(f"[PARSE_RESUME] Extracted {len(extracted_text)} characters from document")
        except ValueError as e:
            logger.error(f"[PARSE_RESUME] Document extraction failed: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        
        # Convert text to structured JSON using LLM
        try:
            resume_json = parse_resume_text_to_json(extracted_text)
            logger.info(f"[PARSE_RESUME] Successfully parsed resume to JSON")
            
            return {
                "success": True,
                "message": "Resume parsed successfully",
                "resume_data": resume_json,
                "extracted_text_length": len(extracted_text)
            }
            
        except ValueError as e:
            logger.error(f"[PARSE_RESUME] LLM parsing failed: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to parse resume content: {str(e)}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[PARSE_RESUME] Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def search_jobs_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for job postings across multiple job boards
    Uses 24-hour cache to reduce redundant scraping
    
    Request body:
    {
        "job_title": "data analyst",
        "location": "remote OR us",
        "date_posted": "posted today",
        "sources": ["workday", "greenhouse", "lever"],
        "max_results": 20
    }
    
    Response:
    {
        "success": true,
        "total_results": 15,
        "jobs": [...],
        "cached": true/false,
        "cached_at": "2025-01-15T10:30:00" (if cached)
    }
    """
    try:
        # Parse request body
        data = await request.json()
        
        # Extract parameters
        job_title = data.get("job_title", "").strip()
        location = data.get("location", "remote OR us")
        date_posted = data.get("date_posted", "posted today")
        sources = data.get("sources", ["workday"])
        max_results = data.get("max_results", 20)
        
        # Validation
        if not job_title:
            raise HTTPException(status_code=400, detail="Job title is required")
        
        if not isinstance(sources, list) or len(sources) == 0:
            raise HTTPException(status_code=400, detail="At least one source must be selected")
        
        logger.info(f"[API_JOB_SEARCH] User '{current_user['username']}' searching: '{job_title}' in '{location}'")
        
        # Generate cache key
        cache_key = generate_cache_key(job_title, location, date_posted, sources)
        logger.info(f"[API_JOB_SEARCH] Cache key: {cache_key}")
        
        # Check cache first
        cached_result = get_cached_job_search(db, cache_key)
        
        if cached_result:
            logger.info(f"[API_JOB_SEARCH] Cache HIT - returning {len(cached_result['jobs'])} cached jobs (hits: {cached_result['hit_count']})")
            return {
                "success": True,
                "total_results": cached_result['total_results'],
                "jobs": cached_result['jobs'],
                "cached": True,
                "cached_at": cached_result['cached_at'],
                "expires_at": cached_result['expires_at'],
                "cache_hits": cached_result['hit_count'],
                "search_query": {
                    "job_title": job_title,
                    "location": location,
                    "date_posted": date_posted,
                    "sources": sources
                }
            }
        
        # Cache miss - perform fresh scrape
        logger.info(f"[API_JOB_SEARCH] Cache MISS - scraping fresh results")
        jobs = await job_scraper.search_jobs(
            job_title=job_title,
            location=location,
            date_posted=date_posted,
            sources=sources,
            max_results=max_results
        )
        
        # Store in cache (24 hour TTL)
        store_job_search_cache(
            db=db,
            cache_key=cache_key,
            job_title=job_title,
            location=location,
            sources=sources,
            jobs=jobs,
            ttl_hours=24
        )
        
        logger.info(f"[API_JOB_SEARCH] Returning {len(jobs)} fresh jobs (cached for 24h)")
        
        return {
            "success": True,
            "total_results": len(jobs),
            "jobs": jobs,
            "cached": False,
            "search_query": {
                "job_title": job_title,
                "location": location,
                "date_posted": date_posted,
                "sources": sources
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_JOB_SEARCH] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Job search failed: {str(e)}")


async def scrape_job_details_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Scrape full job description from a job posting URL
    Caches scraped descriptions to reduce redundant requests
    
    Request body:
    {
        "url": "https://company.myworkdayjobs.com/..."
    }
    
    Response:
    {
        "success": true,
        "job_details": {
            "title": "...",
            "company": "...",
            "description": "..."
        },
        "cached": true/false
    }
    """
    try:
        # Parse request body
        data = await request.json()
        
        url = data.get("url", "").strip()
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        # Validate URL
        if not url.startswith('http'):
            raise HTTPException(status_code=400, detail="Invalid URL")
        
        logger.info(f"[API_SCRAPE_JOB] User '{current_user['username']}' scraping: {url}")
        
        # Check if description is already cached
        cached_description = get_job_description(db, url)
        
        if cached_description:
            logger.info(f"[API_SCRAPE_JOB] Cache HIT - returning cached description")
            # Parse cached data (assuming format matches scraper output)
            return {
                "success": True,
                "job_details": {
                    "description": cached_description,
                    "url": url
                },
                "cached": True
            }
        
        # Cache miss - scrape fresh
        logger.info(f"[API_SCRAPE_JOB] Cache MISS - scraping fresh description")
        job_details = await job_scraper.scrape_job_details(url)
        
        if not job_details:
            raise HTTPException(status_code=404, detail="Failed to scrape job details. URL may be invalid or blocked.")
        
        # Store in database for future use
        try:
            store_job_posting(
                db=db,
                job_url=url,
                title=job_details.get('title', 'Unknown'),
                company=job_details.get('company', 'Unknown'),
                location=job_details.get('location', 'Unknown'),
                source=job_details.get('source', 'unknown'),
                snippet=job_details.get('description', '')[:500],  # First 500 chars as snippet
                full_description=job_details.get('description', '')
            )
            logger.info(f"[API_SCRAPE_JOB] Cached job description for future use")
        except Exception as cache_error:
            # Don't fail the request if caching fails
            logger.warning(f"[API_SCRAPE_JOB] Failed to cache description: {cache_error}")
        
        logger.info(f"[API_SCRAPE_JOB] Successfully scraped job: {job_details.get('title', 'Unknown')}")
        
        return {
            "success": True,
            "job_details": job_details,
            "cached": False
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_SCRAPE_JOB] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to scrape job details: {str(e)}")


# Cache Management Endpoints

async def get_cache_stats_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get job search cache statistics
    Useful for monitoring cache performance and popular searches
    
    Response:
    {
        "success": true,
        "stats": {
            "total_cache_entries": 150,
            "active_entries": 120,
            "expired_entries": 30,
            "total_cache_hits": 450,
            "popular_searches": [...]
        }
    }
    """
    try:
        logger.info(f"[API_CACHE_STATS] User '{current_user['username']}' requesting cache stats")
        
        stats = get_cache_stats(db)
        
        return {
            "success": True,
            "stats": stats
        }
    
    except Exception as e:
        logger.error(f"[API_CACHE_STATS] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


async def clear_cache_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear job search cache
    Options:
    - Clear all cache
    - Clear expired cache only
    - Clear specific search
    
    Request body:
    {
        "action": "all" | "expired" | "specific",
        "cache_key": "..." (required if action="specific")
    }
    
    Response:
    {
        "success": true,
        "cleared_count": 25,
        "message": "..."
    }
    """
    try:
        data = await request.json()
        action = data.get("action", "expired")
        
        logger.info(f"[API_CLEAR_CACHE] User '{current_user['username']}' clearing cache (action: {action})")
        
        if action == "expired":
            # Clear only expired entries
            cleared_count = cleanup_expired_cache(db)
            message = f"Cleared {cleared_count} expired cache entries"
        
        elif action == "all":
            # Clear all cache entries
            cleared_count = db.query(JobSearchCache).delete()
            db.commit()
            message = f"Cleared all {cleared_count} cache entries"
        
        elif action == "specific":
            # Clear specific cache entry
            cache_key = data.get("cache_key", "").strip()
            if not cache_key:
                raise HTTPException(status_code=400, detail="cache_key required for specific action")
            
            cleared_count = db.query(JobSearchCache).filter(
                JobSearchCache.search_key == cache_key
            ).delete()
            db.commit()
            
            if cleared_count == 0:
                message = "Cache entry not found"
            else:
                message = f"Cleared cache entry: {cache_key}"
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'all', 'expired', or 'specific'")
        
        logger.info(f"[API_CLEAR_CACHE] {message}")
        
        return {
            "success": True,
            "cleared_count": cleared_count,
            "message": message
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_CLEAR_CACHE] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


async def refresh_cache_endpoint(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Force refresh specific cached search
    Scrapes fresh results and updates cache
    
    Request body:
    {
        "job_title": "data analyst",
        "location": "remote OR us",
        "date_posted": "posted today",
        "sources": ["workday"]
    }
    
    Response:
    {
        "success": true,
        "message": "Cache refreshed",
        "total_results": 15
    }
    """
    try:
        data = await request.json()
        
        job_title = data.get("job_title", "").strip()
        location = data.get("location", "remote OR us")
        date_posted = data.get("date_posted", "posted today")
        sources = data.get("sources", ["workday"])
        max_results = data.get("max_results", 20)
        
        if not job_title:
            raise HTTPException(status_code=400, detail="job_title is required")
        
        logger.info(f"[API_REFRESH_CACHE] User '{current_user['username']}' refreshing cache for: '{job_title}'")
        
        # Generate cache key
        cache_key = generate_cache_key(job_title, location, date_posted, sources)
        
        # Delete existing cache entry
        db.query(JobSearchCache).filter(
            JobSearchCache.search_key == cache_key
        ).delete()
        db.commit()
        
        # Scrape fresh results
        jobs = await job_scraper.search_jobs(
            job_title=job_title,
            location=location,
            date_posted=date_posted,
            sources=sources,
            max_results=max_results
        )
        
        # Store fresh results
        store_job_search_cache(
            db=db,
            cache_key=cache_key,
            job_title=job_title,
            location=location,
            sources=sources,
            jobs=jobs,
            ttl_hours=24
        )
        
        logger.info(f"[API_REFRESH_CACHE] Cache refreshed with {len(jobs)} jobs")
        
        return {
            "success": True,
            "message": "Cache refreshed successfully",
            "total_results": len(jobs),
            "jobs": jobs
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_REFRESH_CACHE] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh cache: {str(e)}")
