# app/main.py
import os
import json
import logging
from typing import Dict, List, Any
import re
import tempfile
import random
import traceback
from datetime import datetime
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.create_resume import create_resume
from app.database import (
    get_db, init_db, User, ResumeJob, UserResumeTemplate,
    create_user, authenticate_user, SessionLocal
)

from app.utils import ( 
    normalize_whitespace,
    split_resume_sections, chat_completion, parse_experience_to_json, parse_skills_to_json
)

from app.prompts import (
    JD_HINTS_PROMPT, SCORING_PROMPT_JSON, APPLY_EDITS_PROMPT,
    BALANCE_BULLETS_PROMPT, ORGANIZE_SKILLS_PROMPT, GENERATE_FROM_JD_PROMPT,
)

# --------------------- App Setup ---------------------
app = FastAPI(title="Resume Tailor MVP")

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()

# --------------------- Logging Setup ---------------------
import os
import sys

# Configure logging - only to console for production
log_handlers = [logging.StreamHandler(sys.stdout)]

# Only add file logging in local development
if os.environ.get('ENVIRONMENT') != 'production':
    os.makedirs('debug_files', exist_ok=True)
    log_handlers.append(logging.FileHandler(os.path.join('debug_files', 'app.log')))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)

logger = logging.getLogger(__name__)

# Create and configure debug directory
debug_dir = os.path.join(os.getcwd(), "debug_files")
try:
    # Create directory with proper permissions
    os.makedirs(debug_dir, exist_ok=True)
    os.chmod(debug_dir, 0o755)  # rwxr-xr-x permissions
    
    # Test directory is writable
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
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

# Health check endpoint for deployment platforms
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and auto-wake on free tiers"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "max_workers": int(os.getenv("MAX_WORKERS", "2")),
        "max_concurrent_jobs": int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
    }

# --------------------- Static Files & Dashboard ---------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main index.html with integrated dashboard"""
    index_path = Path(__file__).parent.parent / "index.html"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(
            content="<h1>Resume Builder not found</h1><p>Please ensure index.html exists in the project root.</p>",
            status_code=404
        )

# Global dict to track job progress in memory
job_progress = {}

def send_progress(request_id: str, progress: int, status_message: str, db: Session = None):
    """Update job progress in database and memory
    
    Args:
        request_id: The job request ID
        progress: Progress percentage (0-100)
        status_message: Descriptive message about current step
        db: Database session
    """
    # Store progress and message in memory (don't store status state here)
    job_progress[request_id] = {
        "progress": progress,
        "message": status_message
    }
    logger.info(f"Job {request_id}: {progress}% - {status_message}")
    
    if db:
        try:
            job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id).first()
            if job:
                job.progress = progress
                job.status = "processing" if progress < 100 else "completed"
                if progress == 100:
                    job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update job progress: {str(e)}")

# Dependency to get current user
async def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

# --------------------- Helpers ---------------------
def extract_json(text: str) -> dict:
    """Extract JSON from text that might contain other content."""
    try:
        # First try direct JSON parsing
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON between curly braces
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None

def _save_debug_file(content: Any, filename: str, prefix: str = "debug") -> None:
    """Save content to a debug file with timestamp."""
    try:
        debug_dir = os.path.join(os.getcwd(), "debug_files")
        
        # Ensure directory exists and is writable
        os.makedirs(debug_dir, exist_ok=True)
        if not os.access(debug_dir, os.W_OK):
            os.chmod(debug_dir, 0o755)
            
        # Generate unique filename with timestamp only until minute precision
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        full_filename = f"{prefix}__{timestamp}_{safe_filename}"
        filepath = os.path.join(debug_dir, full_filename)
        
        # Save content with appropriate formatting
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, ensure_ascii=False, indent=2)
        else:
            content_str = str(content)
            
        # Add metadata header
        header = f"""# Debug File
        # Generated: {datetime.now().isoformat()}
        # Type: {type(content).__name__}
        # File: {filename}
        # Prefix: {prefix}
        # {"="*50}
        """
        # Write content with header
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + content_str)
            
        # Set file permissions
        os.chmod(filepath, 0o644)
        
        # Verify file
        if not os.path.exists(filepath):
            raise Exception(f"File was not created: {filepath}")
            
        file_size = os.path.getsize(filepath)
        logger.info(f"[debug] Saved {prefix} to {filepath} ({file_size} bytes)")
        
        # List all debug files periodically
        if random.random() < 0.1:  # 10% chance to list files
            files = os.listdir(debug_dir)
            logger.info(f"[debug] Current debug files ({len(files)}): {', '.join(files[:5])}...")
            
    except Exception as e:
        logger.error(f"[debug] Failed to save debug file {filename}")
        logger.error(f"[debug] Error: {str(e)}")
        logger.error(f"[debug] Traceback: {traceback.format_exc()}")
        # Try alternate location
        try:
            alt_path = os.path.join(tempfile.gettempdir(), full_filename)
            with open(alt_path, 'w', encoding='utf-8') as f:
                f.write(content_str)
            logger.info(f"[debug] Saved to alternate location: {alt_path}")
        except Exception as e2:
            logger.error(f"[debug] Alternate save also failed: {str(e2)}")

def _balance_experience_roles(experience_json: List[dict], jd_hints: str) -> List[dict]:
    """
    Balance each role's bullet points between 6-8 bullets using the structured JSON format.
    Each role in experience_json should have: company, title, date, and bullets fields.
    """
    if not experience_json:
        return experience_json

    balanced_roles = []
    for role in experience_json:
        bullets = role.get("bullets", [])
        if 6 <= len(bullets) <= 8:
            balanced_roles.append(role)
            continue

        # Balance bullets using LLM
        bullets_text = "\n".join(f"- {b}" for b in bullets)
        prompt = BALANCE_BULLETS_PROMPT.format(jd_hints=jd_hints, section_text=bullets_text)
        balanced_text = chat_completion(prompt)
        
        # Parse balanced bullets back into list
        new_bullets = [
            b.strip("- ").strip() 
            for b in balanced_text.split("\n") 
            if b.strip().startswith(("-", "•", "*"))
        ]
        
        logger.info(
            "[balance] Role: '%s' bullets %d → %d",
            role.get("title", "Unknown"),
            len(bullets),
            len(new_bullets)
        )
        
        # Create new role with balanced bullets
        balanced_role = dict(role)  # Create a copy
        balanced_role["bullets"] = new_bullets
        balanced_roles.append(balanced_role)
    
    return balanced_roles


def _safe_load_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        i, j = raw.find("{"), raw.rfind("}")
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(raw[i:j+1])
            except Exception:
                pass
    return None

def _norm_section_name(name: str) -> str:
    n = (name or "").strip().lower()
    for ch in [":", "-", "|", "—"]:
        n = n.replace(ch, " ")
    n = " ".join(n.split())
    if "summary" in n or "professional summary" in n:
        return "summary"
    if "skill" in n or "technical skill" in n:
        return "skills"
    if "experience" in n or "work experience" in n or "professional experience" in n:
        return "experience"
    if "project" in n:
        return "projects"
    if "education" in n:
        return "education"
    if "cert" in n:
        return "certifications"
    return n


def convert_resume_json_to_text(resume_data: dict) -> str:
    """Convert structured resume JSON into clean plain-text format."""

    lines = []

    # --- Header ---
    name = resume_data.get("name", "")
    contact = resume_data.get("contact", "")
    
    # Handle both string and structured contact formats
    if isinstance(contact, dict):
        # Structured format: build contact line from dict
        contact_parts = []
        ordered_keys = ["phone", "email", "linkedin", "github", "portfolio", "website"]
        
        # Add ordered items first
        for key in ordered_keys:
            if key in contact and contact[key]:
                contact_parts.append(contact[key] if key in ["phone", "email"] else key.capitalize())
        
        # Add any additional links
        for key, value in contact.items():
            if key not in ordered_keys and value:
                contact_parts.append(key.capitalize())
        
        contact_line = " | ".join(contact_parts)
    else:
        # String format: use as-is
        contact_line = contact
    
    lines.append(f"{name.upper()}\n{contact_line}\n")

    # --- Summary ---
    if resume_data.get("summary"):
        lines.append("SUMMARY\n")
        lines.append(resume_data["summary"].strip() + "\n")

    # --- Technical Skills ---
    if resume_data.get("technical_skills"):
        lines.append("TECHNICAL SKILLS\n")
        for key, value in resume_data["technical_skills"].items():
            if value.strip():
                lines.append(f"{key}: {value}")
        lines.append("")

    # --- Experience ---
    if resume_data.get("experience"):
        lines.append("EXPERIENCE\n")
        for exp in resume_data["experience"]:
            company = exp.get("company", "")
            role = exp.get("role", "")
            period = exp.get("period", "")
            lines.append(f"{company} | {role} | {period}")
            for point in exp.get("points", []):
                lines.append(f"  • {point}")
            lines.append("")

    # --- Education ---
    if resume_data.get("education"):
        lines.append("EDUCATION\n")
        for edu in resume_data["education"]:
            degree = edu.get("degree", "")
            institution = edu.get("institution", "")
            year = edu.get("year", "")
            lines.append(f"{degree}\n{institution} ({year})\n")

    return "\n".join(lines)

# --------------------- Endpoints ---------------------
from fastapi import HTTPException
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Create a thread pool for CPU-bound operations
# Optimized for free tier deployment (512 MB RAM limit)
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))  # Default: 2 for free tier, increase for production
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# --------------------- Auth Endpoints ---------------------

@app.post("/api/auth/register")
async def register(
    request: Request,
    db: Session = Depends(get_db)
):
    """Register new user"""
    try:
        user_data = await request.json()
        user_id = user_data.get("user_id")
        password = user_data.get("password")
        
        if not user_id or not password:
            raise HTTPException(status_code=400, detail="user_id and password required")
        
        # Check if user exists
        existing_user = db.query(User).filter(User.user_id == user_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create user
        user = create_user(db, user_id, password)
        
        return {
            "message": "User created successfully",
            "user_id": user.user_id,
            "created_at": user.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login")
async def login(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Login user"""
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"}
        )
    
    return {
        "message": "Login successful",
        "user_id": user.user_id,
        "last_login": user.last_login.isoformat() if user.last_login else None
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1"
    }

# --------------------- Resume Generation Endpoints ---------------------

@app.post("/api/generate_resume_json")
@limiter.limit("5/minute")  # Max 5 requests per minute per IP
async def generate_resume_json(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate resume with job tracking and rate limiting"""
    try:
        # Check user limits (configurable for different deployment tiers)
        MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))  # Default: 2 for free tier, 3+ for production
        # No daily limit - users can create unlimited resumes
        
        # Count active jobs for this user
        active_jobs = db.query(ResumeJob).filter(
            ResumeJob.user_id == current_user.user_id,
            ResumeJob.status.in_(["pending", "processing"])
        ).count()
        
        if active_jobs >= MAX_CONCURRENT_JOBS:
            raise HTTPException(
                status_code=429,
                detail=f"Too many concurrent jobs. You have {active_jobs} jobs processing. Please wait for them to complete."
            )
        
        data = await request.json()
        request_id = data.get("request_id", f"req_{int(time.time())}_{current_user.user_id}")
        
        # Create resume job record
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
        
        logger.info(f"Created resume job {resume_job.id} for user {current_user.user_id}")
        
        # Process resume in background
        background_tasks.add_task(
            process_resume_background,
            data,
            request_id,
            resume_job.id
        )
        
        return {
            "message": "Resume generation started",
            "request_id": request_id,
            "job_id": resume_job.id,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting resume generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def process_resume_background(data: dict, request_id: str, job_id: int):
    """Background task to process resume"""
    db = SessionLocal()
    try:
        # Update status to processing
        job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
        if job:
            job.status = "processing"
            
            # Increment active jobs counter
            user = db.query(User).filter(User.user_id == job.user_id).first()
            if user:
                user.active_jobs_count = (user.active_jobs_count or 0) + 1
            
            db.commit()
        
        # Process resume
        result = process_resume(data, request_id, db)
        
        # Update job with final result
        if job:
            job.final_resume_json = result
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            
            # Update user stats
            user = db.query(User).filter(User.user_id == job.user_id).first()
            if user:
                user.total_resumes_generated = (user.total_resumes_generated or 0) + 1
                user.active_jobs_count = max(0, (user.active_jobs_count or 1) - 1)
            
            db.commit()
            
        logger.info(f"Resume generation completed for job {job_id}")
        
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}\n{traceback.format_exc()}")
        
        # Update job with error
        job = db.query(ResumeJob).filter(ResumeJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            
            # Decrement active jobs counter on failure
            user = db.query(User).filter(User.user_id == job.user_id).first()
            if user:
                user.active_jobs_count = max(0, (user.active_jobs_count or 1) - 1)
            
            db.commit()
    finally:
        db.close()

def process_resume(data: dict, request_id: str = None, db: Session = None) -> dict:

    """Process resume in thread pool - this is the CPU-intensive part"""
    send_progress(request_id, 5, "Starting resume processing...", db)
    
    resume_json = data.get("resume_data", {})
    
    # Extract job description - handle both old and new payload formats
    # New format: { jd: "...", company_name: "...", job_title: "..." }
    # Old format: { job_description_data: { job_description: "...", company_name: "..." } }
    if "job_description_data" in data:
        # Old format for backwards compatibility
        job_json = data.get("job_description_data", {})
        jd = job_json.get("job_description", "")
        company_name = job_json.get("company_name", "")
    else:
        # New format - direct fields
        jd = data.get("jd", "")
        company_name = data.get("company_name", "")
    
    mode = data.get("mode", "complete_jd")  # Extract mode, default to 'complete_jd'
    
    logger.info(f"[MODE] Processing resume in '{mode}' mode")
    logger.info(f"[JD] Job description length: {len(jd)} chars")
    logger.info(f"[COMPANY] Company name: {company_name}")

    final_json = {}
    name = resume_json.get("name", "")
    final_json["name"] = name
    contact = resume_json.get("contact", "")
    final_json["contact"] = contact
    education = resume_json.get("education", [])
    final_json["education"] = education
    
    send_progress(request_id, 10, "Processing basic information...", db)
    
    # Add projects if present and not empty (filter out objects with empty fields)
    projects = resume_json.get("projects", [])
    if projects:
        # Filter out projects with empty title or no bullets
        valid_projects = [
            p for p in projects 
            if p.get("title", "").strip() and p.get("bullets") and len(p.get("bullets", [])) > 0
        ]
        if valid_projects:
            final_json["projects"] = valid_projects
    
    # Add certifications if present and not empty (filter out objects with empty fields)
    certifications = resume_json.get("certifications", [])
    if certifications:
        # Filter out certifications with empty name
        valid_certifications = [
            c for c in certifications 
            if c.get("name", "").strip()
        ]
        if valid_certifications:
            final_json["certifications"] = valid_certifications

    # convert resume_json to text format if needed
    resume_txt = convert_resume_json_to_text(resume_json)

    # write debug files
    # _save_debug_file(resume_txt, "resume_text.txt", prefix="resume")

    # jd and company_name already extracted above
    jd_file_name = company_name.replace(" ", "_") + ".txt" if company_name else "job_description.txt"
    # save jd file
    _save_debug_file(jd, jd_file_name, prefix="job_description")

    resume_text = normalize_whitespace(resume_txt)
    # _save_debug_file(resume_text, "normalized_resume_text.txt", prefix="resume_normalized")
    sections = split_resume_sections(resume_text)
    #_save_debug_file(sections, "resume_sections.json", prefix="resume_sections")

    # Plan + JD hints
    plan_prompt = SCORING_PROMPT_JSON.replace("{jd_text}", jd).replace("{resume_text}", resume_text)    
    plan_raw = chat_completion(plan_prompt)
    plan = _safe_load_json(plan_raw) or {"section_updates": []}
    
    # Debug: Log the scoring plan
    logger.info(f"[SCORING PLAN] Received {len(plan.get('section_updates', []))} section updates")
    for update in plan.get("section_updates", []):
        section_name = update.get("section", "Unknown")
        logger.info(f"[SCORING PLAN] - Section: {section_name}")
    
    jd_hints = chat_completion(JD_HINTS_PROMPT.format(jd_text=jd))
    #save jd_hints
    #_save_debug_file(jd_hints, "jd_hints.txt", prefix="jd_hints")

    # Apply plan (same as /api/tailor)
    rewritten: Dict[str, str] = {}
    updates = plan.get("section_updates", [])

    # Process Summary section
    if sections.get("Summary"):
        summary_edits = [e for e in updates if _norm_section_name(e.get("section")) == "summary"]
        logger.info(f"[SUMMARY] Found {len(summary_edits)} summary edits from scoring plan")
        
        # ALWAYS process summary
        if mode == "complete_jd":
            # Use GENERATE_FROM_JD_PROMPT for complete JD mode
            logger.info("[SUMMARY] Using GENERATE_FROM_JD_PROMPT (complete_jd mode)")
            send_progress(request_id, 40, "Generating summary...", db)
            prompt = GENERATE_FROM_JD_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Summary"],
                section_edits_json=json.dumps(summary_edits, ensure_ascii=False) if summary_edits else "[]"
            )
        else:  # resume_jd mode
            # Use APPLY_EDITS_PROMPT for resume + JD mode
            logger.info("[SUMMARY] Using APPLY_EDITS_PROMPT (resume_jd mode)")
            send_progress(request_id, 40, "Optimizing summary...", db)
            prompt = APPLY_EDITS_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Summary"],
                section_edits_json=json.dumps(summary_edits, ensure_ascii=False) if summary_edits else "[]"
            )
        rewritten["Summary"] = chat_completion(prompt).strip()
        logger.info("[SUMMARY] Summary section rewritten successfully")
        
    # Process Skills section
    if sections.get("Skills"):
        send_progress(request_id, 60, "Processing skills...", db)
        skills_edits = [e for e in updates if _norm_section_name(e.get("section")) == "skills"]
        logger.info(f"[SKILLS] Found {len(skills_edits)} skills edits from scoring plan")
        
        # ALWAYS process skills, even if LLM didn't include it in scoring plan
        if mode == "complete_jd":
            # Use GENERATE_FROM_JD_PROMPT for complete JD mode
            logger.info("[SKILLS] Using GENERATE_FROM_JD_PROMPT (complete_jd mode)")
            prompt = GENERATE_FROM_JD_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Skills"],
                section_edits_json=json.dumps(skills_edits, ensure_ascii=False) if skills_edits else "[]"
            )
        else:  # resume_jd mode
            # Use APPLY_EDITS_PROMPT for resume + JD mode
            logger.info("[SKILLS] Using APPLY_EDITS_PROMPT (resume_jd mode)")
            prompt = APPLY_EDITS_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Skills"],
                section_edits_json=json.dumps(skills_edits, ensure_ascii=False) if skills_edits else "[]"
            )
        rewritten["Skills"] = chat_completion(prompt).strip()
        logger.info("[SKILLS] Skills section rewritten successfully")
    else:
        logger.warning("[SKILLS] No Skills section found in parsed resume sections")

    # Process Experience section
    send_progress(request_id, 75, "Optimizing experience section...", db)
    if sections.get("Experience"):
        experience_edits = [e for e in updates if _norm_section_name(e.get("section")) == "experience"]
        logger.info(f"[EXPERIENCE] Found {len(experience_edits)} experience edits from scoring plan")
        
        # ALWAYS process experience
        if mode == "complete_jd":
            # Use GENERATE_FROM_JD_PROMPT for complete JD mode
            logger.info("[EXPERIENCE] Using GENERATE_FROM_JD_PROMPT (complete_jd mode)")
            prompt = GENERATE_FROM_JD_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Experience"],
                section_edits_json=json.dumps(experience_edits, ensure_ascii=False) if experience_edits else "[]"
            )
        else:  # resume_jd mode
            # Use APPLY_EDITS_PROMPT for resume + JD mode
            logger.info("[EXPERIENCE] Using APPLY_EDITS_PROMPT (resume_jd mode)")
            prompt = APPLY_EDITS_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Experience"],
                section_edits_json=json.dumps(experience_edits, ensure_ascii=False) if experience_edits else "[]"
            )
        rewritten["Experience"] = chat_completion(prompt).strip()
        logger.info("[EXPERIENCE] Experience section rewritten successfully")
       
        
        # Save intermediate experience for debugging
        #_save_debug_file(rewritten["Experience"], "experience_after_rewrite.txt", prefix="experience")
    
    # _save_debug_file(rewritten, "rewritten_sections.json", prefix="rewritten_sections")
    
    # get summary from rewritten into final_json
    if rewritten.get("Summary"):
        final_json["summary"] = rewritten["Summary"]

    # Enhancements (Experience + Skills) for DOCX too
    if rewritten.get("Experience"):
        # First parse to JSON structure

        experience_json = parse_experience_to_json(rewritten["Experience"])
        # print(f"\n\n experience_json before balancing: {experience_json} \n\n")
        logger.info(f"[EXPERIENCE] Parsed experience JSON: {experience_json}")

        # Apply enhancements using JSON structure
        new_experience_json = _balance_experience_roles(experience_json, jd_hints)
        # print(f"\n\nnew_experience_json: {new_experience_json}\n\n")
        logger.info("[EXPERIENCE] Balanced experience JSON")

        #add experience to final_json
        final_json["experience"] = new_experience_json

    if rewritten.get("Skills"):
        # First parse to JSON structure
        skills_json = parse_skills_to_json(rewritten["Skills"])
        logger.info(f"[SKILLS] Parsed skills JSON: {skills_json}")
        # print(f"\n\n skills_json before formatting: {skills_json} \n\n")
        # Apply formatting using JSON structure
        prompt = ORGANIZE_SKILLS_PROMPT.format(skills_json=json.dumps(skills_json, ensure_ascii=False, indent=2))
        response = chat_completion(prompt)

        # Optional safety parsing
        def extract_json(text):
            match = re.search(r"\{.*\}", text, re.DOTALL)
            return json.loads(match.group(0)) if match else None

        organized_skills = extract_json(response)
        # print(f"skills_json after formatting: {organized_skills} \n\n")
        logger.info(f"[SKILLS] Organized skills JSON: {organized_skills}")
        final_json["technical_skills"] = organized_skills
    else:
        # Fallback: Use original skills from resume_json if rewrite failed
        logger.warning("[SKILLS] No Skills section in rewritten content, using original")
        final_json["technical_skills"] = resume_json.get("technical_skills", {})

    send_progress(request_id, 95, "Finalizing resume...", db)
    send_progress(request_id, 100, "Resume completed!", db)
    logger.info(f"[COMPLETE] Resume processing finished successfully")

    return final_json


# --------------------- Job Status & Management Endpoints ---------------------

@app.get("/api/jobs/{request_id}/status")
async def get_job_status(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    
    # Use database status (processing/completed/failed) not the message
    # Get progress from memory (more real-time) or database
    current_progress = memory_progress.get("progress", job.progress)
    status_message = memory_progress.get("message", "")
    
    return {
        "job_id": job.id,
        "request_id": job.request_id,
        "status": job.status,  # Use DB status (processing/completed/failed)
        "progress": current_progress,  # Use memory progress for real-time updates
        "message": status_message,  # Optional: current step message
        "company_name": job.company_name,
        "job_title": job.job_title,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message
    }

@app.get("/api/jobs/{request_id}/result")
async def get_job_result(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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

@app.get("/api/jobs/{request_id}/download")
async def download_resume(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate and download resume DOCX on-the-fly (in-memory, no file storage)"""
    job = db.query(ResumeJob).filter(
        ResumeJob.request_id == request_id,
        ResumeJob.user_id == current_user.user_id
    ).first()
    
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="Completed job not found")
    
    if not job.final_resume_json:
        raise HTTPException(status_code=404, detail="Resume data not found")
    
    try:
        # Generate DOCX in memory using BytesIO
        import io
        from docx import Document
        
        # Create a temporary file path for create_resume function
        # We'll still use the function but read the file into memory
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
            tmp_path = tmp_file.name
        
        # Generate the resume
        create_resume(job.final_resume_json, tmp_path)
        
        # Read the file into memory
        with open(tmp_path, 'rb') as f:
            docx_content = f.read()
        
        # Delete the temporary file
        import os
        os.unlink(tmp_path)
        
        # Create filename
        filename = f"{job.company_name}_{job.job_title}_Resume.docx".replace(" ", "_").replace("/", "_")
        
        # Return as streaming response (no file storage needed)
        from fastapi.responses import Response
        return Response(
            content=docx_content,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
            
    except Exception as e:
        logger.error(f"Error generating DOCX: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate DOCX: {str(e)}")

@app.get("/api/jobs/{request_id}/download-jd")
async def download_job_description(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the job description as a text file"""
    job = db.query(ResumeJob).filter(
        ResumeJob.request_id == request_id,
        ResumeJob.user_id == current_user.user_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.jd_text:
        raise HTTPException(status_code=404, detail="Job description not found")
    
    try:
        from fastapi.responses import Response
        
        # Create filename
        filename = f"{job.company_name}_{job.job_title}_JD.txt".replace(" ", "_").replace("/", "_")
        
        # Return as text file
        return Response(
            content=job.jd_text,
            media_type='text/plain',
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
            
    except Exception as e:
        logger.error(f"Error downloading JD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download JD: {str(e)}")

@app.get("/api/user/jobs")
async def get_user_jobs(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
            for job in jobs
        ]
    }

@app.get("/api/user/stats")
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user statistics and limits"""
    # Refresh user from db to get latest stats
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    
    # Count today's resumes
    from datetime import timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_resumes = db.query(ResumeJob).filter(
        ResumeJob.user_id == current_user.user_id,
        ResumeJob.created_at >= today_start,
        ResumeJob.status == "completed"
    ).count()
    
    # Count active jobs
    active_jobs = db.query(ResumeJob).filter(
        ResumeJob.user_id == current_user.user_id,
        ResumeJob.status.in_(["pending", "processing"])
    ).count()
    
    max_concurrent = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
    
    return {
        "user_id": user.user_id,
        "total_resumes": user.total_resumes_generated or 0,
        "today_resumes": today_resumes,
        "active_jobs": active_jobs,
        "limits": {
            "max_concurrent_jobs": max_concurrent,
            "rate_limit": "5 requests per minute"
        },
        "remaining": {
            "concurrent_slots": max(0, max_concurrent - active_jobs)
        },
        "account_created": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None
    }

@app.post("/api/user/resume-template")
async def save_resume_template(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save or update user's resume template"""
    try:
        # Get the request body
        data = await request.json()
        
        # Extract resume_data from the payload
        # Frontend sends: { resume_data: {...} }
        resume_data = data.get("resume_data", data)
        
        logger.info(f"[SAVE TEMPLATE] User: {current_user.user_id}")
        logger.info(f"[SAVE TEMPLATE] Resume data keys: {list(resume_data.keys())}")
        
        # Check if template already exists
        template = db.query(UserResumeTemplate).filter(
            UserResumeTemplate.user_id == current_user.user_id
        ).first()
        
        if template:
            # Update existing template
            logger.info(f"[SAVE TEMPLATE] Updating existing template")
            template.resume_data = resume_data
            template.updated_at = datetime.utcnow()
        else:
            # Create new template
            logger.info(f"[SAVE TEMPLATE] Creating new template")
            template = UserResumeTemplate(
                user_id=current_user.user_id,
                resume_data=resume_data
            )
            db.add(template)
        
        db.commit()
        db.refresh(template)
        
        return {
            "message": "Resume template saved successfully",
            "updated_at": template.updated_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving resume template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save resume template: {str(e)}")

@app.get("/api/user/resume-template")
async def get_resume_template(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's saved resume template"""
    logger.info(f"[LOAD TEMPLATE] User: {current_user.user_id}")
    
    template = db.query(UserResumeTemplate).filter(
        UserResumeTemplate.user_id == current_user.user_id
    ).first()
    
    if not template:
        logger.info(f"[LOAD TEMPLATE] No template found for user {current_user.user_id}")
        return {
            "has_template": False,
            "resume_data": None
        }
    
    # Handle both old nested format and new flat format
    resume_data = template.resume_data
    
    # If data has "resume_data" key (old nested format), unwrap it
    if isinstance(resume_data, dict) and "resume_data" in resume_data:
        logger.info(f"[LOAD TEMPLATE] Unwrapping nested resume_data structure")
        resume_data = resume_data["resume_data"]
    
    logger.info(f"[LOAD TEMPLATE] Template found, keys: {list(resume_data.keys()) if resume_data else 'None'}")
    
    return {
        "has_template": True,
        "resume_data": resume_data,
        "updated_at": template.updated_at.isoformat()
    }

