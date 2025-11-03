# app/endpoints.py
# Additional API endpoints for job management

from fastapi import HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db, User, ResumeJob
from app.create_resume import create_resume
import logging

logger = logging.getLogger("resume_tailor")

async def get_job_status_endpoint(
    request_id: str,
    current_user: User,
    db: Session,
    job_progress: dict
):
    """Get job status and progress"""
    job = db.query(ResumeJob).filter(
        ResumeJob.request_id == request_id,
        ResumeJob.user_id == current_user.user_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get real-time progress from memory if available
    memory_progress = job_progress.get(request_id, {})
    
    return {
        "job_id": job.id,
        "request_id": job.request_id,
        "status": memory_progress.get("status", job.status),
        "progress": memory_progress.get("progress", job.progress),
        "company_name": job.company_name,
        "job_title": job.job_title,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message
    }

async def get_job_result_endpoint(
    request_id: str,
    current_user: User,
    db: Session
):
    """Get completed resume JSON"""
    job = db.query(ResumeJob).filter(
        ResumeJob.request_id == request_id,
        ResumeJob.user_id == current_user.user_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed. Status: {job.status}")
    
    return {
        "job_id": job.id,
        "request_id": job.request_id,
        "company_name": job.company_name,
        "job_title": job.job_title,
        "final_resume": job.final_resume_json,
        "completed_at": job.completed_at.isoformat()
    }

async def download_resume_endpoint(
    request_id: str,
    current_user: User,
    db: Session
):
    """Generate and download resume DOCX on-the-fly"""
    job = db.query(ResumeJob).filter(
        ResumeJob.request_id == request_id,
        ResumeJob.user_id == current_user.user_id
    ).first()
    
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="Completed job not found")
    
    try:
        # Generate DOCX on-the-fly
        filename = f"{job.company_name}_{current_user.user_id}_resume.docx"
        create_resume(job.final_resume_json, filename)
        
        # Return file for download
        file_path = Path(filename)
        if file_path.exists():
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to generate DOCX")
            
    except Exception as e:
        logger.error(f"Error generating DOCX: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_user_jobs_endpoint(
    limit: int,
    current_user: User,
    db: Session
):
    """Get user's job history"""
    jobs = db.query(ResumeJob).filter(
        ResumeJob.user_id == current_user.user_id
    ).order_by(ResumeJob.created_at.desc()).limit(limit).all()
    
    return {
        "count": len(jobs),
        "jobs": [
            {
                "job_id": job.id,
                "request_id": job.request_id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "mode": job.mode,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
            for job in jobs
        ]
    }
