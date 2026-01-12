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
from app.auth import get_current_user, get_current_user_optional
from app.create_resume import create_resume
from app.job_processing import (
    process_resume_parallel, job_progress, send_progress,
    extract_jd_keywords, generate_resume_content,
    load_intermediate_state, cleanup_expired_intermediate_states
)
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
            # Set application_status to resume_generated on successful completion
            if not job.application_status:
                job.application_status = "resume_generated"
                job.last_status_update = datetime.utcnow()
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
            # Set application_status to resume_generated even on failure (user can still track it)
            if not job.application_status:
                job.application_status = "resume_generated"
                job.last_status_update = datetime.utcnow()
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
        
        # Get format selection (default to classic for backward compatibility)
        resume_format = data.get("format", "classic")
        if resume_format not in ["classic", "modern"]:
            resume_format = "classic"
        
        # Get job_link if provided
        job_link = data.get("job_link", None)
        
        resume_job = ResumeJob(
            user_id=current_user.user_id,
            request_id=request_id,
            company_name=company_name,
            job_title=job_title,
            mode=data.get("mode", "complete_jd"),
            format=resume_format,
            jd_text=jd_text,
            resume_input_json=data.get("resume_data", {}),
            status="pending",
            progress=0,
            job_link=job_link
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


async def extract_keywords_from_jd(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 1: Extract JD keywords and pause for human feedback.
    Returns extracted keywords for user review/editing.
    """
    try:
        MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
        active_jobs = db.query(ResumeJob).filter(
            ResumeJob.user_id == current_user.user_id,
            ResumeJob.status.in_(["pending", "processing", "awaiting_feedback"])
        ).count()
        if active_jobs >= MAX_CONCURRENT_JOBS:
            raise HTTPException(status_code=429, detail=f"Too many concurrent jobs")
        
        data = await request.json()
        
        # Validate input payload
        validation_errors = validate_resume_payload(data)
        if validation_errors:
            raise HTTPException(status_code=400, detail=f"Validation failed: {'; '.join(validation_errors)}")
        
        request_id = data.get("request_id", f"req_{int(time.time())}_{current_user.user_id}")
        
        # Extract job description data
        job_data = data.get("job_description_data", {})
        company_name = job_data.get("company_name") or data.get("company_name", "Unknown")
        job_title = job_data.get("job_title") or data.get("job_title", "Unknown")
        jd_text = job_data.get("job_description") or data.get("jd", "")
        
        # Get format selection
        resume_format = data.get("format", "classic")
        if resume_format not in ["classic", "modern"]:
            resume_format = "classic"
        
        # Get job_link if provided
        job_link = data.get("job_link", None)
        
        # Get mode with tracing
        mode_from_request = data.get("mode", "complete_jd")
        logger.info(f"[MODE_TRACE] ===== EXTRACT_KEYWORDS_FROM_JD ENDPOINT =====")
        logger.info(f"[MODE_TRACE] Request ID: {request_id}")
        logger.info(f"[MODE_TRACE] Mode received from frontend: '{mode_from_request}'")
        logger.info(f"[MODE_TRACE] User: {current_user.user_id}")
        
        # Create job record
        mode_value = data.get("mode", "complete_jd")
        logger.info(f"[EXTRACT_KEYWORDS] Creating job with mode: '{mode_value}'")
        
        resume_job = ResumeJob(
            user_id=current_user.user_id,
            request_id=request_id,
            company_name=company_name,
            job_title=job_title,
            mode=mode_from_request,
            format=resume_format,
            jd_text=jd_text,
            resume_input_json=data.get("resume_data", {}),
            status="processing",
            progress=0,
            job_link=job_link
        )
        db.add(resume_job)
        db.commit()
        db.refresh(resume_job)
        
        logger.info(f"[MODE_TRACE] Mode saved to DB job record: '{resume_job.mode}'")
        
        # Extract keywords (Phase 1)
        result = await extract_jd_keywords(data, request_id, db)
        
        # Update job status to awaiting_feedback
        resume_job.status = "awaiting_feedback"
        resume_job.progress = 25
        
        # Store the full intermediate state (not just user-facing result)
        # Load the full state from memory which includes jd, preprocessed_jd, etc.
        try:
            full_state = load_intermediate_state(request_id, db)
            logger.info(f"[MODE_TRACE] Mode in full_state after extract: '{full_state.get('mode', 'NOT_SET')}'")
            resume_job.intermediate_state = full_state
        except ValueError:
            # Fallback: if loading from memory fails, reconstruct full state
            logger.warning(f"[EXTRACT_KEYWORDS] Failed to load intermediate state, reconstructing from input data")
            resume_job.intermediate_state = {
                "request_id": request_id,
                "resume_json": data.get("resume_data", {}),
                "jd": jd_text,
                "company_name": company_name,
                "job_title": job_title,
                "mode": mode_value,
                **result  # Merge in the extracted keywords
            }
        db.commit()
        
        return {
            "message": "Keywords extracted successfully",
            "request_id": request_id,
            "job_id": resume_job.id,
            "keywords": result
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error extracting keywords: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


async def regenerate_keywords(
    request_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate keywords for an existing job in awaiting_feedback status.
    Uses the stored intermediate state to re-run JD keyword extraction.
    """
    try:
        # Find the job
        job = db.query(ResumeJob).filter(
            ResumeJob.request_id == request_id,
            ResumeJob.user_id == current_user.user_id
        ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status != "awaiting_feedback":
            raise HTTPException(
                status_code=400,
                detail=f"Can only regenerate keywords for jobs awaiting feedback (current status: {job.status})"
            )
        
        # Load intermediate state
        intermediate_data = job.intermediate_state
        if not intermediate_data:
            intermediate_data = load_intermediate_state(request_id, db)
        
        logger.info(f"[MODE_TRACE] Mode in intermediate_data for regenerate: '{intermediate_data.get('mode', 'NOT_SET') if intermediate_data else 'NO_DATA'}'")
        
        if not intermediate_data:
            raise HTTPException(
                status_code=404,
                detail="Original job data not found. The session may have expired."
            )
        
        logger.info(f"[REGENERATE] Regenerating keywords for request_id: {request_id}")
        logger.info(f"[REGENERATE] Intermediate data keys: {list(intermediate_data.keys())}")
        
        # Try to get JD text from multiple sources
        jd_text = intermediate_data.get("jd", "") or job.jd_text or ""
        
        logger.info(f"[REGENERATE] JD text length: {len(jd_text)}")
        logger.info(f"[REGENERATE] Company: {intermediate_data.get('company_name') or job.company_name}")
        logger.info(f"[REGENERATE] Job title: {intermediate_data.get('job_title') or job.job_title}")
        
        if not jd_text:
            logger.error(f"[REGENERATE] JD text is empty in both intermediate_data and job.jd_text")
            raise HTTPException(
                status_code=400,
                detail="Job description text not found in stored data. Cannot regenerate."
            )
        
        # Update progress
        job.progress = 15
        db.commit()
        send_progress(request_id, 15, "Regenerating keywords...", db)
        
        # Reconstruct the original data payload for re-extraction
        # Use data from intermediate_state or fallback to job record
        original_data = {
            "job_description_data": {
                "job_description": jd_text,
                "company_name": intermediate_data.get("company_name") or job.company_name,
                "job_title": intermediate_data.get("job_title") or job.job_title
            },
            "resume_data": intermediate_data.get("resume_json") or job.resume_input_json or {},
            "mode": intermediate_data.get("mode") or job.mode or "complete_jd"
        }
        
        logger.info(f"[REGENERATE] Reconstructed data - JD length: {len(jd_text)}, mode: {original_data['mode']}")
        
        # Re-run keyword extraction
        result = await extract_jd_keywords(original_data, request_id, db)
        
        # Update job with new keywords - preserve full state structure
        full_state = load_intermediate_state(request_id, db)
        if full_state:
            # Update only the keyword portion of the full state
            logger.info(f"[MODE_TRACE] Mode after keyword regeneration: '{full_state.get('mode', 'NOT_SET')}'")
            job.intermediate_state = full_state
        else:
            # Fallback: store the result but ensure resume_data is included
            logger.warning(f"[REGENERATE] Failed to load intermediate state, reconstructing")
            job.intermediate_state = {
                "request_id": request_id,
                "resume_json": intermediate_data.get("resume_json") or job.resume_input_json or {},
                "jd": jd_text,
                "company_name": intermediate_data.get("company_name") or job.company_name,
                "job_title": intermediate_data.get("job_title") or job.job_title,
                "mode": intermediate_data.get("mode") or job.mode or "complete_jd",
                **result  # Merge in the new keywords
            }
        job.progress = 25
        db.commit()
        
        send_progress(request_id, 25, "Keywords regenerated - Review updated", db)
        
        logger.info(f"[REGENERATE] Keywords regenerated successfully for request_id: {request_id}")
        
        return {
            "message": "Keywords regenerated successfully",
            "request_id": request_id,
            "job_id": job.id,
            "keywords": result
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error regenerating keywords: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


async def generate_resume_with_feedback(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 2: Generate resume with user-approved keywords.
    Accepts request_id and optional feedback modifications.
    """
    try:
        data = await request.json()
        
        request_id = data.get("request_id")
        if not request_id:
            raise HTTPException(status_code=400, detail="request_id is required")
        
        # Validate request belongs to user
        resume_job = db.query(ResumeJob).filter(
            ResumeJob.request_id == request_id,
            ResumeJob.user_id == current_user.user_id
        ).first()
        
        if not resume_job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if resume_job.status not in ["awaiting_feedback"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Job is not awaiting feedback (current status: {resume_job.status})"
            )
        
        # Validate feedback format (if provided)
        feedback = data.get("feedback")
        if feedback:
            validation_errors = validate_feedback_data(feedback)
            if validation_errors:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid feedback format: {'; '.join(validation_errors)}"
                )
            logger.info(f"[FEEDBACK] User provided keyword edits for request {request_id}")
        else:
            logger.info(f"[FEEDBACK] No feedback provided - using original extracted keywords for request {request_id}")
        
        # Update job status
        resume_job.status = "processing"
        resume_job.progress = 30
        resume_job.feedback_submitted_at = datetime.utcnow()
        db.commit()
        
        # Start background generation
        background_tasks.add_task(
            generate_resume_background,
            request_id,
            feedback,
            resume_job.id
        )
        
        return {
            "message": "Resume generation started with feedback",
            "request_id": request_id,
            "job_id": resume_job.id
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error generating resume with feedback: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


def generate_resume_background(request_id: str, feedback: dict, job_id: int):
    """Background task for Phase 2 generation"""
    db = SessionLocal()
    try:
        job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        # Update user active jobs count
        user = db.query(User).filter(User.user_id == job.user_id).first()
        if user:
            user.active_jobs_count = (user.active_jobs_count or 0) + 1
        db.commit()
        
        # Generate resume with feedback
        result = asyncio.run(generate_resume_content(request_id, feedback, db))
        
        # Update job with results
        job.final_resume_json = result
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        job.intermediate_state = None  # Clear intermediate state
        
        if user:
            user.total_resumes_generated = (user.total_resumes_generated or 0) + 1
            user.active_jobs_count = max(0, (user.active_jobs_count or 1) - 1)
        
        db.commit()
        logger.info(f"Resume generation with feedback completed for job {job_id}")
        
    except Exception as e:
        logger.error(f"Error in feedback background processing: {str(e)}")
        logger.error(traceback.format_exc())
        
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


def validate_feedback_data(feedback: dict) -> list:
    """
    Validate feedback data structure.
    Returns list of error messages (empty if valid).
    """
    errors = []
    
    if not isinstance(feedback, dict):
        errors.append("Feedback must be a JSON object")
        return errors
    
    # Check for required keys
    if "technical_keywords" not in feedback:
        errors.append("technical_keywords is required")
    elif not isinstance(feedback["technical_keywords"], list):
        errors.append("technical_keywords must be an array")
    
    if "soft_skills" not in feedback:
        errors.append("soft_skills is required")
    elif not isinstance(feedback["soft_skills"], list):
        errors.append("soft_skills must be an array")
    
    if "phrases" not in feedback:
        errors.append("phrases is required")
    elif not isinstance(feedback["phrases"], list):
        errors.append("phrases must be an array")
    
    # Validate array contents are strings
    if "technical_keywords" in feedback and isinstance(feedback["technical_keywords"], list):
        for idx, item in enumerate(feedback["technical_keywords"]):
            if not isinstance(item, str):
                errors.append(f"technical_keywords[{idx}] must be a string")
    
    if "soft_skills" in feedback and isinstance(feedback["soft_skills"], list):
        for idx, item in enumerate(feedback["soft_skills"]):
            if not isinstance(item, str):
                errors.append(f"soft_skills[{idx}] must be a string")
    
    if "phrases" in feedback and isinstance(feedback["phrases"], list):
        for idx, item in enumerate(feedback["phrases"]):
            if not isinstance(item, str):
                errors.append(f"phrases[{idx}] must be a string")
    
    return errors


async def cleanup_expired_states_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to cleanup expired intermediate states.
    Removes states older than configured TTL.
    """
    try:
        ttl_hours = int(os.getenv("INTERMEDIATE_STATE_TTL_HOURS", "2"))
        
        # Cleanup in-memory states
        cleanup_expired_intermediate_states(ttl_hours)
        
        # Cleanup DB persisted states
        cutoff_time = datetime.utcnow() - timedelta(hours=ttl_hours)
        expired_jobs = db.query(ResumeJob).filter(
            ResumeJob.status == "awaiting_feedback",
            ResumeJob.created_at < cutoff_time
        ).all()
        
        count = 0
        for job in expired_jobs:
            job.status = "failed"
            job.error_message = "Session expired - feedback not provided within time limit"
            job.intermediate_state = None
            count += 1
        
        db.commit()
        
        return {
            "message": "Cleanup completed",
            "expired_jobs_marked_failed": count,
            "ttl_hours": ttl_hours
        }
    except Exception as e:
        logger.error(f"Error cleaning up expired states: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_job_status(request_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id, ResumeJob.user_id == current_user.user_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    memory_progress = job_progress.get(request_id, {})
    return {"job_id": job.id, "request_id": job.request_id, "status": job.status, "progress": memory_progress.get("progress", job.progress), "message": memory_progress.get("message", ""), "company_name": job.company_name, "job_title": job.job_title, "created_at": job.created_at.isoformat(), "completed_at": job.completed_at.isoformat() if job.completed_at else None, "error_message": job.error_message}


async def get_job_keywords(request_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve stored keywords from intermediate_state for awaiting_feedback jobs"""
    job = db.query(ResumeJob).filter(
        ResumeJob.request_id == request_id,
        ResumeJob.user_id == current_user.user_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "awaiting_feedback":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting feedback (current status: {job.status})"
        )
    
    # Get keywords from intermediate_state (DB) or memory
    keywords = job.intermediate_state
    if not keywords:
        # Try to load from memory as fallback
        keywords = load_intermediate_state(request_id, db)
    
    logger.info(f"[MODE_TRACE] Mode in keywords response: '{keywords.get('mode', 'NOT_SET') if keywords else 'NO_KEYWORDS'}'")
    
    if not keywords:
        raise HTTPException(
            status_code=404,
            detail="Keywords not found. The session may have expired."
        )
    
    return {
        "request_id": request_id,
        "job_id": job.id,
        "keywords": keywords,
        "company_name": job.company_name,
        "job_title": job.job_title
    }


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


async def download_resume(
    request_id: str, 
    format: str = "classic",  # Accept format as query parameter
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id, ResumeJob.user_id == current_user.user_id).first()
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="Completed job not found")
    try:
        # Use format from query parameter (allows downloading same resume in different formats)
        # Validate format value
        if format not in ["classic", "modern"]:
            format = "classic"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
            tmp_path = tmp_file.name
        create_resume(job.final_resume_json, tmp_path, format=format)
        with open(tmp_path, 'rb') as f:
            docx_content = f.read()
        os.unlink(tmp_path)
        filename = f"{job.company_name}_{job.job_title}_Resume_{format}.docx".replace(" ", "_").replace("/", "_")
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
    date_range: str = None,
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
    
    # Apply date range filter
    if date_range:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        
        if date_range == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == "week":
            start_date = now - timedelta(days=7)
        elif date_range == "month":
            start_date = now - timedelta(days=30)
        elif date_range == "3months":
            start_date = now - timedelta(days=90)
        elif date_range == "6months":
            start_date = now - timedelta(days=180)
        elif date_range == "year":
            start_date = now - timedelta(days=365)
        else:
            start_date = None
        
        if start_date:
            query = query.filter(ResumeJob.created_at >= start_date)
    
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
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "job_link": job.job_link,
                "application_status": job.application_status or "resume_generated",
                "application_date": job.application_date.isoformat() if job.application_date else None,
                "application_notes": job.application_notes,
                "last_status_update": job.last_status_update.isoformat() if job.last_status_update else None
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
    current_user = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Search for jobs across multiple sources
    Automatically uses JSearch API if available (real job data), 
    otherwise falls back to web scraping or sample data
    Uses 24-hour cache to reduce redundant API calls
    
    Request body:
    {
        "job_title": "data analyst",
        "location": "remote OR us", 
        "date_posted": "posted today",
        "sources": ["workday", "greenhouse", "lever"],
        "max_results": 20
    }
    
    Note: JSearch API provides real job data when JSEARCH_API_KEY is configured
    
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
        
        # New dynamic parameters
        employment_types = data.get("employment_types", ["FULLTIME"])
        experience_level = data.get("experience_level", "")
        work_from_home = data.get("work_from_home", False)
        salary_min = data.get("salary_min")
        salary_max = data.get("salary_max")
        salary_frequency = data.get("salary_frequency", "yearly")
        sort_by = data.get("sort_by", "relevance")  # "relevance" or "date"
        
        # Validation
        if not job_title:
            raise HTTPException(status_code=400, detail="Job title is required")
        
        if not isinstance(sources, list) or len(sources) == 0:
            raise HTTPException(status_code=400, detail="At least one source must be selected")
        
        user_id = current_user.user_id if current_user else 'anonymous'
        logger.info(f"[API_JOB_SEARCH] User '{user_id}' searching: '{job_title}' in '{location}'")
        
        # Generate cache key
        cache_key = generate_cache_key(job_title, location, date_posted, sources, sort_by)
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
            max_results=max_results,
            employment_types=employment_types,
            experience_level=experience_level,
            work_from_home=work_from_home,
            salary_min=salary_min,
            salary_max=salary_max,
            sort_by=sort_by
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


async def search_greenhouse_jobs_endpoint(
    request: Request,
    current_user = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Search for jobs specifically from Greenhouse company boards
    High-quality jobs from tech companies like Databricks, Stripe, Snowflake, etc.
    
    Request body:
    {
        "job_title": "data engineer",
        "location": "remote",
        "max_results": 20,
        "company_tokens": ["databricks", "stripe", "snowflake"]  // optional
    }
    
    Response:
    {
        "success": true,
        "total_results": 15,
        "jobs": [...],
        "companies_searched": ["databricks", "stripe", ...]
    }
    """
    try:
        data = await request.json()
        
        job_title = data.get("job_title", "").strip()
        location = data.get("location", "").strip()
        max_results = min(data.get("max_results", 20), 50)  # Cap at 50
        company_tokens = data.get("company_tokens", None)
        employment_types = data.get("employment_types", [])
        remote_jobs_only = data.get("remote_jobs_only", False)
        date_posted = data.get("date_posted", "all")
        
        # Validate required fields
        if not job_title:
            raise HTTPException(status_code=400, detail="job_title is required")
        
        logger.info(f"[API_GREENHOUSE] Searching: '{job_title}' in '{location}' (max: {max_results})")
        logger.info(f"[API_GREENHOUSE] Filters - Types: {employment_types}, Remote only: {remote_jobs_only}, Date: {date_posted}")
        
        # Search Greenhouse companies
        jobs = await job_scraper._search_greenhouse_companies(
            job_title=job_title,
            location=location,
            max_results=max_results,
            company_tokens=company_tokens,
            employment_types=employment_types,
            remote_jobs_only=remote_jobs_only,
            date_posted=date_posted
        )
        
        # Get list of companies that were searched
        default_companies = [
            "databricks", "stripe", "snowflake", "nvidia", "tiktok", 
            "canva", "instacart", "doordash", "coinbase", "robinhood",
            "discord", "figma", "notion", "airtable", "palantir"
        ]
        searched_companies = company_tokens[:10] if company_tokens else default_companies[:10]
        
        logger.info(f"[API_GREENHOUSE] Found {len(jobs)} jobs from {len(searched_companies)} companies")
        
        return {
            "success": True,
            "total_results": len(jobs),
            "jobs": jobs,
            "companies_searched": searched_companies,
            "search_params": {
                "job_title": job_title,
                "location": location,
                "max_results": max_results
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API_GREENHOUSE] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Greenhouse job search failed: {str(e)}")


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
        
        logger.info(f"[API_SCRAPE_JOB] User '{current_user.user_id}' scraping: {url}")
        
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
        
        if not job_details or not job_details.get('description'):
            # Return partial success with warning
            logger.warning(f"[API_SCRAPE_JOB] Scraping failed for {url}")
            return {
                "success": True,
                "job_details": {
                    "title": "",
                    "company": "",
                    "description": "",
                    "url": url
                },
                "cached": False,
                "warning": "Could not scrape job description. Please paste manually."
            }
        
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
        logger.info(f"[API_CACHE_STATS] Public request for cache stats")
        
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
        
        logger.info(f"[API_CLEAR_CACHE] Public request to clear cache (action: {action})")
        
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
        
        logger.info(f"[API_REFRESH_CACHE] Public request to refresh cache for: '{job_title}'")
        
        # Generate cache key (use default sort for refresh)
        cache_key = generate_cache_key(job_title, location, date_posted, sources, "relevance")
        
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
            max_results=max_results,
            sort_by="relevance"
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


# ===== EMAIL GENERATION ENDPOINTS =====

async def email_generate(request: Request, current_user: User = Depends(get_current_user_optional)):
    """
    Generate professional emails based on user request.
    Supports both template-based and custom (freeform) email generation.
    
    Request Body:
    {
        "email_type": "custom" | "job_application" | "reply" | "followup" | "thankyou" | 
                      "networking" | "salary_negotiation" | "resignation" | "referral_request" |
                      "decline_offer" | "feedback_request" | "interview_scheduling",
        "tone": "professional" | "enthusiastic" | "formal" | "conversational" | "friendly" | "assertive",
        "length": "short" | "medium" | "long",
        
        // For custom emails
        "custom_request": "Natural language description of email needed",
        "context": "Additional context or details",
        
        // For template-based emails
        "company": "Company name",
        "job_title": "Job title",
        "jd": "Job description text",
        "recruiter_email": "Recruiter's email content (for replies)",
        
        // Optional
        "include_resume": true/false
    }
    
    Returns:
    {
        "subject": "Email subject line",
        "body": "Email body content",
        "timestamp": "2024-01-01T12:00:00"
    }
    """
    from app.email_generator import (
        generate_custom_email, 
        generate_template_email, 
        get_user_resume_summary
    )
    
    try:
        data = await request.json()
        
        email_type = data.get("email_type", "custom")
        tone = data.get("tone", "professional")
        length = data.get("length", "medium")
        include_resume = data.get("include_resume", False)
        
        # Validate inputs
        if email_type not in ["custom", "job_application", "reply", "followup", "thankyou", 
                               "networking", "salary_negotiation", "resignation", "referral_request",
                               "decline_offer", "feedback_request", "interview_scheduling"]:
            raise HTTPException(status_code=400, detail=f"Invalid email_type: {email_type}")
        
        if tone not in ["professional", "enthusiastic", "formal", "conversational", "friendly", "assertive"]:
            raise HTTPException(status_code=400, detail=f"Invalid tone: {tone}")
        
        if length not in ["short", "medium", "long"]:
            raise HTTPException(status_code=400, detail=f"Invalid length: {length}")
        
        # Get resume data if user is logged in (for both summary and signature)
        resume_summary = None
        resume_data = None
        if current_user:
            try:
                # Try to get from session/latest template
                db = next(get_db())
                template = db.query(UserResumeTemplate).filter(
                    UserResumeTemplate.user_id == current_user.user_id
                ).order_by(UserResumeTemplate.updated_at.desc()).first()
                
                if template and template.resume_data:
                    resume_data = template.resume_data
                    # Only include resume summary in email if requested
                    if include_resume:
                        resume_summary = get_user_resume_summary(template.resume_data)
                db.close()
            except Exception as e:
                logger.warning(f"Could not load resume for user {current_user.user_id}: {e}")
        
        # Generate email based on type
        if email_type == "custom":
            # Custom/freeform email
            custom_request = data.get("custom_request", "").strip()
            context = data.get("context", "")
            
            if not custom_request or len(custom_request) < 10:
                raise HTTPException(
                    status_code=400, 
                    detail="custom_request is required and must be at least 10 characters"
                )
            
            logger.info(f"Generating custom email - User: {current_user.user_id if current_user else 'anonymous'}, Length: {len(custom_request)} chars")
            
            result = await generate_custom_email(
                request=custom_request,
                context=context,
                resume_summary=resume_summary,
                tone=tone,
                length=length,
                resume_data=resume_data
            )
        else:
            # Template-based email
            company = data.get("company", "")
            job_title = data.get("job_title", "")
            jd = data.get("jd", "")
            recruiter_email = data.get("recruiter_email", "")
            context = data.get("context", "")
            
            logger.info(f"Generating {email_type} email - User: {current_user.user_id if current_user else 'anonymous'}")
            
            result = await generate_template_email(
                email_type=email_type,
                company=company,
                job_title=job_title,
                jd=jd,
                resume_summary=resume_summary,
                tone=tone,
                length=length,
                recruiter_email=recruiter_email,
                context=context,
                resume_data=resume_data
            )
        
        return {
            "subject": result["subject"],
            "body": result["body"],
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate email: {str(e)}")


# --------------------- Application Tracking Endpoints ---------------------

async def update_application_status(
    resume_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the application status of a resume job.
    Accepts: application_status, application_date (optional), application_notes (optional)
    """
    try:
        data = await request.json()
        
        # Fetch the resume job
        resume_job = db.query(ResumeJob).filter(
            ResumeJob.id == resume_id,
            ResumeJob.user_id == current_user.user_id
        ).first()
        
        if not resume_job:
            raise HTTPException(status_code=404, detail="Resume job not found")
        
        # Validate status
        valid_statuses = ["resume_generated", "applied", "rejected", "screening", "interview", "offer"]
        application_status = data.get("application_status")
        if application_status and application_status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Update fields
        if application_status:
            resume_job.application_status = application_status
            resume_job.last_status_update = datetime.utcnow()
        
        if "application_date" in data:
            app_date = data["application_date"]
            if app_date:
                try:
                    resume_job.application_date = datetime.fromisoformat(app_date.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    raise HTTPException(status_code=400, detail="Invalid application_date format")
            else:
                resume_job.application_date = None
        
        if "application_notes" in data:
            resume_job.application_notes = data.get("application_notes")
        
        if "job_link" in data:
            resume_job.job_link = data.get("job_link")
        
        db.commit()
        db.refresh(resume_job)
        
        return {
            "message": "Application status updated successfully",
            "resume_id": resume_job.id,
            "application_status": resume_job.application_status,
            "application_date": resume_job.application_date.isoformat() if resume_job.application_date else None,
            "last_status_update": resume_job.last_status_update.isoformat() if resume_job.last_status_update else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating application status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def get_application_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get application statistics for the current user.
    Returns counts by status and recent applications.
    """
    try:
        # Get all resume jobs for the user
        all_jobs = db.query(ResumeJob).filter(
            ResumeJob.user_id == current_user.user_id
        ).all()
        
        # Count by status
        stats = {
            "total_applications": len(all_jobs),
            "resume_generated": 0,
            "applied": 0,
            "rejected": 0,
            "screening": 0,
            "interview": 0,
            "offer": 0
        }
        
        for job in all_jobs:
            status = job.application_status or "resume_generated"
            if status in stats:
                stats[status] += 1
        
        # Get recent applications (last 10)
        recent_jobs = db.query(ResumeJob).filter(
            ResumeJob.user_id == current_user.user_id
        ).order_by(ResumeJob.created_at.desc()).limit(10).all()
        
        recent_applications = []
        for job in recent_jobs:
            recent_applications.append({
                "id": job.id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "application_status": job.application_status or "resume_generated",
                "application_date": job.application_date.isoformat() if job.application_date else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "job_link": job.job_link
            })
        
        return {
            "stats": stats,
            "recent_applications": recent_applications
        }
    
    except Exception as e:
        logger.error(f"Error getting application stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
