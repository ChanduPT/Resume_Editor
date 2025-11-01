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
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.create_resume import create_resume

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------- Logging Setup ---------------------


# Setup enhanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG level to capture all logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(os.path.join('debug_files', 'app.log'))  # Log to file
    ]
)
logger = logging.getLogger("resume_tailor")

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
executor = ThreadPoolExecutor(max_workers=4)

@app.post("/api/generate_resume_json")
async def generate_resume_json(request: Request):
    
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    # Run CPU-intensive operations in thread pool to not block event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, process_resume, data)
    
    return result

def process_resume(data: dict) -> dict:
    """Process resume in thread pool - this is the CPU-intensive part"""
    resume_json = data.get("resume_data", {})
    job_json = data.get("job_description_data", {})
    mode = data.get("mode", "complete_jd")  # Extract mode, default to 'complete_jd'
    
    logger.info(f"[MODE] Processing resume in '{mode}' mode")

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

    # _save_debug_file(final_json, "final_resume_json.json", prefix="final_resume_json")

    comapny_name = job_json.get("company_name", "Company")
    # file name - company_name_date_time.docx
    file_name = f"{comapny_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"


    create_resume(final_json, file_name)

    return {"result": "Resume generated successfully", "file_name": file_name}
