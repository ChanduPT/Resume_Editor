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

from app.database import get_db, User, ResumeJob, UserResumeTemplate, SessionLocal
from app.auth import get_current_user
from app.create_resume import create_resume
from app.job_processing import process_resume_parallel, job_progress

logger = logging.getLogger(__name__)


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
        request_id = data.get("request_id", f"req_{int(time.time())}_{current_user.user_id}")
        resume_job = ResumeJob(
            user_id=current_user.user_id,
            request_id=request_id,
            company_name=data.get("company_name", "Unknown"),
            job_title=data.get("job_title", "Unknown"),
            mode=data.get("mode", "complete_jd"),
            jd_text=data.get("jd", ""),
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


async def get_user_jobs(limit: int = 20, offset: int = 0, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get total count
    total_count = db.query(ResumeJob).filter(ResumeJob.user_id == current_user.user_id).count()
    
    # Get paginated jobs
    jobs = db.query(ResumeJob).filter(ResumeJob.user_id == current_user.user_id).order_by(ResumeJob.created_at.desc()).offset(offset).limit(limit).all()
    
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
