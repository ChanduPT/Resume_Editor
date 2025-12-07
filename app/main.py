# app/main.py
# Main FastAPI application - thin entry point with modular imports

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import init_db
from app.auth import register_user, login_user, reset_password, update_profile
from app.endpoints import (
    generate_resume_json, get_job_status, get_job_keywords, get_job_result, update_job_resume,
    download_resume, download_job_description,
    get_user_jobs, get_user_stats,
    save_resume_template, get_resume_template,
    delete_job, cleanup_stale_jobs, parse_resume_document,
    search_jobs_endpoint, search_greenhouse_jobs_endpoint, scrape_job_details_endpoint,
    get_cache_stats_endpoint, clear_cache_endpoint, refresh_cache_endpoint,
    extract_keywords_from_jd, regenerate_keywords, generate_resume_with_feedback, cleanup_expired_states_endpoint,
    update_application_status, get_application_stats
)

# --------------------- App Setup ---------------------
app = FastAPI(title="Resume Tailor MVP")

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger = logging.getLogger(__name__)
    logger.info(f"Static files mounted from: {static_dir}")

security = HTTPBasic()

# --------------------- Logging Setup ---------------------
log_handlers = [logging.StreamHandler(sys.stdout)]

if os.environ.get('ENVIRONMENT') != 'production':
    os.makedirs('debug_files', exist_ok=True)
    log_handlers.append(logging.FileHandler(os.path.join('debug_files', 'app.log')))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)

logger = logging.getLogger(__name__)

# Setup debug directory
debug_dir = os.path.join(os.getcwd(), "debug_files")
try:
    os.makedirs(debug_dir, exist_ok=True)
    os.chmod(debug_dir, 0o755)
    test_file = os.path.join(debug_dir, '.write_test')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
    logger.info(f"Debug directory ready at: {debug_dir}")
except Exception as e:
    logger.error(f"Failed to setup debug directory: {str(e)}")
    raise

# --------------------- Database Startup ---------------------

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        init_db()
        logger.info("Database initialized successfully")
        logger.info(f"MAX_WORKERS: {os.getenv('MAX_WORKERS', '2')}")
        logger.info(f"MAX_CONCURRENT_JOBS: {os.getenv('MAX_CONCURRENT_JOBS', '2')}")
        
        # Clean up any stale jobs from previous runs
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            cleanup_stale_jobs(db)
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

# --------------------- Static Files ---------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main index.html"""
    index_path = Path(__file__).parent.parent / "index.html"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(
            content="<h1>Resume Builder not found</h1><p>Please ensure index.html exists.</p>",
            status_code=404
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1",
        "max_workers": int(os.getenv("MAX_WORKERS", "2")),
        "max_concurrent_jobs": int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
    }

# --------------------- Auth Endpoints ---------------------

app.post("/api/auth/register")(register_user)
app.post("/api/auth/login")(login_user)
app.post("/api/auth/reset-password")(reset_password)
app.put("/api/auth/update-profile")(update_profile)

# --------------------- Resume Generation Endpoints ---------------------

# Legacy single-phase endpoint (backward compatible)
app.post("/api/generate_resume_json")(limiter.limit("5/minute")(generate_resume_json))

# Two-phase endpoints with human feedback
app.post("/api/resume/extract-keywords")(limiter.limit("5/minute")(extract_keywords_from_jd))
app.post("/api/resume/regenerate-keywords/{request_id}")(limiter.limit("10/minute")(regenerate_keywords))
app.post("/api/resume/generate")(limiter.limit("5/minute")(generate_resume_with_feedback))

# --------------------- Job Management Endpoints ---------------------

app.get("/api/jobs/{request_id}/status")(get_job_status)
app.get("/api/jobs/{request_id}/keywords")(get_job_keywords)
app.get("/api/jobs/{request_id}/result")(get_job_result)
app.put("/api/jobs/{request_id}/update")(update_job_resume)
app.get("/api/jobs/{request_id}/download")(download_resume)
app.get("/api/jobs/{request_id}/download-jd")(download_job_description)
app.delete("/api/jobs/{request_id}")(delete_job)

# Manual cleanup endpoint (for debugging)
@app.post("/api/admin/cleanup-stale-jobs")
async def manual_cleanup():
    """Manually trigger cleanup of stale jobs"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        cleanup_stale_jobs(db)
        return {"message": "Stale jobs cleaned up successfully"}
    finally:
        db.close()

# --------------------- User Endpoints ---------------------

app.get("/api/user/jobs")(get_user_jobs)
app.get("/api/user/stats")(get_user_stats)
app.post("/api/user/resume-template")(save_resume_template)
app.get("/api/user/resume-template")(get_resume_template)

# --------------------- Resume Parsing Endpoint ---------------------

app.post("/api/parse-resume")(limiter.limit("3/minute")(parse_resume_document))

# --------------------- Job Search Endpoints ---------------------

app.post("/api/search-jobs")(limiter.limit("10/minute")(search_jobs_endpoint))
app.post("/api/search-greenhouse-jobs")(limiter.limit("15/minute")(search_greenhouse_jobs_endpoint))
app.post("/api/scrape-job-details")(limiter.limit("10/minute")(scrape_job_details_endpoint))

# --------------------- Cache Management Endpoints ---------------------

app.get("/api/cache/stats")(get_cache_stats_endpoint)
app.post("/api/cache/clear")(clear_cache_endpoint)
app.post("/api/cache/refresh")(refresh_cache_endpoint)

# --------------------- Email Generation Endpoints ---------------------

from app.endpoints import email_generate
app.post("/api/email/generate")(email_generate)

# --------------------- Cleanup Endpoints ---------------------

app.post("/api/admin/cleanup-expired-states")(cleanup_expired_states_endpoint)

# --------------------- Application Tracking Endpoints ---------------------

app.patch("/api/resumes/{resume_id}/application-status")(update_application_status)
app.get("/api/resumes/application-stats")(get_application_stats)
