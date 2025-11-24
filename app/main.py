# app/main.py
# Main FastAPI application - thin entry point with modular imports

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.create_resume import create_resume

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
from app.auth import register_user, login_user, reset_password
from app.endpoints import (
    generate_resume_json, get_job_status, get_job_keywords, get_job_result, update_job_resume,
    download_resume, download_job_description,
    get_user_jobs, get_user_stats,
    save_resume_template, get_resume_template,
    delete_job, cleanup_stale_jobs, parse_resume_document,
    search_jobs_endpoint, search_greenhouse_jobs_endpoint, scrape_job_details_endpoint,
    get_cache_stats_endpoint, clear_cache_endpoint, refresh_cache_endpoint,
    extract_keywords_from_jd, regenerate_keywords, generate_resume_with_feedback, cleanup_expired_states_endpoint
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
from queue import Queue

# Create a thread pool for CPU-bound operations
executor = ThreadPoolExecutor(max_workers=4)

# Global dictionary to track progress for each request
progress_store: Dict[str, Dict[str, Any]] = {}

def send_progress(request_id: str, percentage: int, message: str):
    """Send progress update to the store for a specific request"""
    if request_id:
        progress_store[request_id] = {
            "percentage": percentage,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"[PROGRESS] {request_id}: {percentage}% - {message}")

@app.get("/api/progress/{request_id}")
async def get_progress(request_id: str):
    """Get current progress for a specific request"""
    if request_id in progress_store:
        return progress_store[request_id]
    return {"percentage": 0, "message": "Initializing..."}

@app.post("/api/generate_resume_json")
async def generate_resume_json(request: Request):
    
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    # Extract request_id if provided
    request_id = data.get("request_id")
    
    # Run CPU-intensive operations in thread pool to not block event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, process_resume, data, request_id)
    
    # Clean up progress after completion
    if request_id and request_id in progress_store:
        del progress_store[request_id]
    
    return result

def process_resume(data: dict, request_id: str = None) -> dict:
    """Process resume in thread pool - this is the CPU-intensive part"""
    resume_json = data.get("resume_data", {})
    job_json = data.get("job_description_data", {})
    mode = data.get("mode", "complete_jd")  # Extract mode, default to 'complete_jd'
    
    logger.info(f"[MODE] Processing resume in '{mode}' mode")
    
    if request_id:
        send_progress(request_id, 5, "Starting resume processing...")

    final_json = {}
    name = resume_json.get("name", "")
    final_json["name"] = name
    contact = resume_json.get("contact", "")
    final_json["contact"] = contact
    education = resume_json.get("education", [])
    final_json["education"] = education
    
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
    
    if request_id:
        send_progress(request_id, 10, "Analyzing job description...")

    # write debug files
    # _save_debug_file(resume_txt, "resume_text.txt", prefix="resume")

    jd = job_json.get("job_description", "")
    jd_file_name = job_json.get("company_name", "job_description").replace(" ", "_") + ".txt"
    # save jd file
    _save_debug_file(jd, jd_file_name, prefix="job_description")

    resume_text = normalize_whitespace(resume_txt)
    # _save_debug_file(resume_text, "normalized_resume_text.txt", prefix="resume_normalized")
    sections = split_resume_sections(resume_text)
    #_save_debug_file(sections, "resume_sections.json", prefix="resume_sections")

    if request_id:
        send_progress(request_id, 20, "Generating optimization plan...")

    # Plan + JD hints
    plan_prompt = SCORING_PROMPT_JSON.replace("{jd_text}", jd).replace("{resume_text}", resume_text)    
    plan_raw = chat_completion(plan_prompt)
    plan = _safe_load_json(plan_raw) or {"section_updates": []}
    
    if request_id:
        send_progress(request_id, 30, "Extracting key insights from job description...")
    
    # Debug: Log the scoring plan
    logger.info(f"[SCORING PLAN] Received {len(plan.get('section_updates', []))} section updates")
    for update in plan.get("section_updates", []):
        section_name = update.get("section", "Unknown")
        logger.info(f"[SCORING PLAN] - Section: {section_name}")
    
    jd_hints = chat_completion(JD_HINTS_PROMPT.format(jd_text=jd))
    #save jd_hints
    #_save_debug_file(jd_hints, "jd_hints.txt", prefix="jd_hints")

    if request_id:
        send_progress(request_id, 40, "Optimizing summary section...")

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
            prompt = GENERATE_FROM_JD_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Summary"],
                section_edits_json=json.dumps(summary_edits, ensure_ascii=False) if summary_edits else "[]"
            )
        else:  # resume_jd mode
            # Use APPLY_EDITS_PROMPT for resume + JD mode
            logger.info("[SUMMARY] Using APPLY_EDITS_PROMPT (resume_jd mode)")
            prompt = APPLY_EDITS_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Summary"],
                section_edits_json=json.dumps(summary_edits, ensure_ascii=False) if summary_edits else "[]"
            )
        rewritten["Summary"] = chat_completion(prompt).strip()
        logger.info("[SUMMARY] Summary section rewritten successfully")
        
    if request_id:
        send_progress(request_id, 55, "Optimizing technical skills...")
        
    # Process Skills section
    if sections.get("Skills"):
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

    if request_id:
        send_progress(request_id, 70, "Optimizing experience section...")

    # Process Experience section
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
    
    if request_id:
        send_progress(request_id, 80, "Structuring final resume data...")
    
    # get summary from rewritten into final_json
    if rewritten.get("Summary"):
        final_json["summary"] = rewritten["Summary"]

    # Enhancements (Experience + Skills) for DOCX too
    if rewritten.get("Experience"):
        # First parse to JSON structure

        experience_json = parse_experience_to_json(rewritten["Experience"])
        # print(f"\n\n experience_json before balancing: {experience_json} \n\n")
        logger.info(f"[EXPERIENCE] Parsed experience JSON: {experience_json}")

        if request_id:
            send_progress(request_id, 85, "Balancing experience bullets...")

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
        
        if request_id:
            send_progress(request_id, 90, "Organizing skills...")
        
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

app.post("/api/search-jobs")(limiter.limit("10/minute")(search_jobs_endpoint))
app.post("/api/search-greenhouse-jobs")(limiter.limit("15/minute")(search_greenhouse_jobs_endpoint))
app.post("/api/scrape-job-details")(limiter.limit("10/minute")(scrape_job_details_endpoint))

    if request_id:
        send_progress(request_id, 95, "Generating Word document...")

    comapny_name = job_json.get("company_name", "Company")
    # file name - company_name_date_time.docx
    file_name = f"{comapny_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

app.get("/api/cache/stats")(get_cache_stats_endpoint)
app.post("/api/cache/clear")(clear_cache_endpoint)
app.post("/api/cache/refresh")(refresh_cache_endpoint)

# --------------------- Cleanup Endpoints ---------------------

    if request_id:
        send_progress(request_id, 100, "Resume generated successfully!")

    return {"result": "Resume generated successfully", "file_name": file_name}
