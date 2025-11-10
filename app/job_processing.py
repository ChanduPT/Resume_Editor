# app/job_processing.py
# Resume processing and job management logic

import json
import logging
import asyncio
from typing import Dict
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import ResumeJob, User
from app.utils import (
    normalize_whitespace, split_resume_sections,
    chat_completion, chat_completion_async,
    parse_experience_to_json, parse_skills_to_json,
    clean_job_description, clean_experience_bullets
)
from app.prompts import (
    JD_HINTS_PROMPT, jd_hints_response_schema,
    GENERATE_SUMMARY_FROM_JD_PROMPT, summary_response_schema,
    GENERATE_EXPERIENCE_FROM_JD_PROMPT, experience_response_schema,
    GENERATE_TECHNICAL_SKILLS_FROM_JD, skills_response_schema,
    SCORING_PROMPT_JSON, APPLY_EDITS_PROMPT,
    ORGANIZE_SKILLS_PROMPT, GENERATE_FROM_JD_PROMPT,
)
from app.helpers import (
    save_debug_file, balance_experience_roles,
    safe_load_json, normalize_section_name,
    convert_resume_json_to_text, extract_json
)

logger = logging.getLogger(__name__)

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


async def process_resume_parallel(data: dict, request_id: str = None, db: Session = None) -> dict:
    """
    Process resume with parallel API calls for faster processing.
    
    Flow:
    1. Extract JD hints (sequential - required for other steps)
    2. Generate summary, experience, skills in parallel
    3. Combine results into final resume JSON
    
    Expected time savings: 40-50% (14-23s → 8-13s)
    """
    send_progress(request_id, 5, "Starting resume processing...", db)
    
    resume_json = data.get("resume_data", {})
    
    # Extract job description - handle both old and new payload formats
    if "job_description_data" in data:
        job_json = data.get("job_description_data", {})
        jd = job_json.get("job_description", "")
        company_name = job_json.get("company_name", "")
    else:
        jd = data.get("jd", "")
        company_name = data.get("company_name", "")
    
    # Clean job description to remove extra spaces and special characters
    jd = clean_job_description(jd)
    
    logger.info(f"[JD] Job description length: {len(jd)} chars (cleaned)")
    logger.info(f"[COMPANY] Company name: {company_name}")

    # Prepare final JSON with static fields
    final_json = {
        "name": resume_json.get("name", ""),
        "contact": resume_json.get("contact", ""),
        "education": resume_json.get("education", [])
    }
    
    send_progress(request_id, 10, "Processing basic information...", db)
    
    # Add projects if present and not empty
    projects = resume_json.get("projects", [])
    if projects:
        valid_projects = [
            p for p in projects 
            if p.get("title", "").strip() and p.get("bullets") and len(p.get("bullets", [])) > 0
        ]
        if valid_projects:
            final_json["projects"] = valid_projects
    
    # Add certifications if present and not empty
    certifications = resume_json.get("certifications", [])
    if certifications:
        valid_certifications = [
            c for c in certifications 
            if c.get("name", "").strip()
        ]
        if valid_certifications:
            final_json["certifications"] = valid_certifications

    # STEP 1: Extract JD hints (SEQUENTIAL - required first)
    send_progress(request_id, 15, "Analyzing job description...", db)
    
    import time
    jd_start = time.time()
    try:
        jd_hints_raw = await chat_completion_async(
            JD_HINTS_PROMPT.format(jd_text=jd),
            response_schema=jd_hints_response_schema,
            timeout=90  # 90 seconds timeout for JD analysis
        )
        jd_hints = json.loads(jd_hints_raw)
        jd_duration = time.time() - jd_start
        logger.info(f"[PERF] JD analysis took {jd_duration:.2f}s - extracted {len(jd_hints.get('technical_keywords', []))} keywords")
    except asyncio.TimeoutError:
        logger.error(f"[JD_HINTS] Timeout after 90 seconds")
        raise Exception("Job description analysis timed out. Please try again.")
    except Exception as e:
        logger.error(f"[JD_HINTS] Error: {str(e)}")
        raise Exception(f"Failed to analyze job description: {str(e)}")
    
    # Get mode from data
    mode = data.get("mode", "complete_jd")
    logger.info(f"[MODE] Processing in '{mode}' mode")
    
    send_progress(request_id, 25, "JD analysis complete. Starting parallel optimization...", db)
    
    # STEP 2: Generate summary, experience, skills in PARALLEL
    async def generate_summary():
        """Generate professional summary from JD hints"""
        try:
            original_summary = resume_json.get("summary", "")
            
            # Use different prompts based on mode
            if mode == "complete_jd":
                logger.info("[SUMMARY] Using GENERATE_SUMMARY_FROM_JD_PROMPT (complete_jd mode)")
                prompt = GENERATE_SUMMARY_FROM_JD_PROMPT.format(
                    jd_hints=json.dumps(jd_hints, ensure_ascii=False),
                    original_summary=original_summary
                )
            else:  # resume_jd mode
                logger.info("[SUMMARY] Using original summary (resume_jd mode)")
                # In resume_jd mode, keep original summary or lightly optimize
                return original_summary if original_summary else "Professional with relevant experience"
            
            result_raw = await chat_completion_async(prompt, response_schema=summary_response_schema, timeout=60)
            result = json.loads(result_raw)
            logger.info("[SUMMARY] Generated successfully")
            return result.get("summary", "")
        except asyncio.TimeoutError:
            logger.error("[SUMMARY] Timeout after 60 seconds")
            return resume_json.get("summary", "")
        except Exception as e:
            logger.error(f"[SUMMARY] Error: {str(e)}")
            return resume_json.get("summary", "")
    
    async def generate_experience():
        """Generate optimized experience bullets from JD hints"""
        try:
            experience_data = resume_json.get("experience", [])
            
            # Use different prompts based on mode
            if mode == "complete_jd":
                logger.info("[EXPERIENCE] Using GENERATE_EXPERIENCE_FROM_JD_PROMPT (complete_jd mode)")
                prompt = GENERATE_EXPERIENCE_FROM_JD_PROMPT.format(
                    technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                    soft_skills=json.dumps(jd_hints.get("soft_skills_role_keywords", []), ensure_ascii=False),
                    phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                    experience_data=json.dumps(experience_data, ensure_ascii=False, indent=2)
                )
            else:  # resume_jd mode
                logger.info("[EXPERIENCE] Using original experience (resume_jd mode - applying light edits)")
                # In resume_jd mode, keep original experience
                return experience_data if experience_data else []
            
            result_raw = await chat_completion_async(prompt, response_schema=experience_response_schema, timeout=90)
            result = json.loads(result_raw)
            experience_result = result.get("experience", [])
            
            # Clean experience bullets to remove markdown and excessive quotes
            experience_result = clean_experience_bullets(experience_result)
            
            logger.info(f"[EXPERIENCE] Generated {len(experience_result)} roles (cleaned)")
            return experience_result
        except asyncio.TimeoutError:
            logger.error("[EXPERIENCE] Timeout after 90 seconds")
            return resume_json.get("experience", [])
        except Exception as e:
            logger.error(f"[EXPERIENCE] Error: {str(e)}")
            return resume_json.get("experience", [])
    
    async def generate_skills():
        """Generate technical skills categorized by JD requirements"""
        try:
            existing_skills = resume_json.get("technical_skills", {})
            
            # Use different prompts based on mode
            if mode == "complete_jd":
                logger.info("[SKILLS] Using GENERATE_TECHNICAL_SKILLS_FROM_JD (complete_jd mode)")
                prompt = GENERATE_TECHNICAL_SKILLS_FROM_JD.format(
                    jd_technical_keywords=", ".join(jd_hints.get("technical_keywords", [])),
                    existing_skills=json.dumps(existing_skills, ensure_ascii=False, indent=2)
                )
            else:  # resume_jd mode
                logger.info("[SKILLS] Using original skills (resume_jd mode)")
                # In resume_jd mode, keep original skills
                return existing_skills if existing_skills else {}
            
            result_raw = await chat_completion_async(prompt, response_schema=skills_response_schema, timeout=60)
            
            # Log raw response to see what model returns
            logger.info(f"[SKILLS] Raw response (first 500 chars): {result_raw[:500]}")
            
            # Use extract_json to handle markdown code blocks
            result = extract_json(result_raw)
            if not result:
                logger.error(f"[SKILLS] Failed to extract JSON from response")
                logger.error(f"[SKILLS] Raw response: {result_raw}")
                return resume_json.get("technical_skills", {})
            
            logger.info(f"[SKILLS] Parsed JSON structure: {list(result.keys())}")
            
            # Extract the nested technical_skills object
            technical_skills = result.get("technical_skills", {})
            logger.info(f"[SKILLS] Generated {len(technical_skills)} categories: {list(technical_skills.keys())}")
            return technical_skills
        except asyncio.TimeoutError:
            logger.error("[SKILLS] Timeout after 60 seconds")
            return resume_json.get("technical_skills", {})
        except Exception as e:
            logger.error(f"[SKILLS] Error: {str(e)}")
            return resume_json.get("technical_skills", {})
    
    # Run all three tasks in parallel
    send_progress(request_id, 30, "Generating summary, experience, and skills in parallel...", db)
    
    summary, experience, skills = await asyncio.gather(
        generate_summary(),
        generate_experience(),
        generate_skills()
    )
    
    send_progress(request_id, 90, "Parallel optimization complete. Finalizing...", db)
    
    # STEP 3: Combine results into final JSON
    final_json["summary"] = summary
    final_json["experience"] = experience
    final_json["technical_skills"] = skills
    
    send_progress(request_id, 100, "Resume completed!", db)
    logger.info(f"[COMPLETE] Parallel resume processing finished successfully")
    
    return final_json


def process_resume(data: dict, request_id: str = None, db: Session = None) -> dict:
    """Process resume in thread pool - this is the CPU-intensive part (DEPRECATED - use process_resume_parallel)"""
    send_progress(request_id, 5, "Starting resume processing...", db)
    
    resume_json = data.get("resume_data", {})
    
    # Extract job description - handle both old and new payload formats
    if "job_description_data" in data:
        job_json = data.get("job_description_data", {})
        jd = job_json.get("job_description", "")
        company_name = job_json.get("company_name", "")
    else:
        jd = data.get("jd", "")
        company_name = data.get("company_name", "")
    
    mode = data.get("mode", "complete_jd")
    
    logger.info(f"[MODE] Processing resume in '{mode}' mode")
    logger.info(f"[JD] Job description length: {len(jd)} chars")
    logger.info(f"[COMPANY] Company name: {company_name}")

    final_json = {
        "name": resume_json.get("name", ""),
        "contact": resume_json.get("contact", ""),
        "education": resume_json.get("education", [])
    }
    
    send_progress(request_id, 10, "Processing basic information...", db)
    
    # Add projects if present and not empty
    projects = resume_json.get("projects", [])
    if projects:
        valid_projects = [
            p for p in projects 
            if p.get("title", "").strip() and p.get("bullets") and len(p.get("bullets", [])) > 0
        ]
        if valid_projects:
            final_json["projects"] = valid_projects
    
    # Add certifications if present and not empty
    certifications = resume_json.get("certifications", [])
    if certifications:
        valid_certifications = [
            c for c in certifications 
            if c.get("name", "").strip()
        ]
        if valid_certifications:
            final_json["certifications"] = valid_certifications

    # Convert resume_json to text format
    resume_txt = convert_resume_json_to_text(resume_json)

    # Save JD file
    jd_file_name = company_name.replace(" ", "_") + ".txt" if company_name else "job_description.txt"
    save_debug_file(jd, jd_file_name, prefix="job_description")

    resume_text = normalize_whitespace(resume_txt)
    sections = split_resume_sections(resume_text)

    # Plan + JD hints
    plan_prompt = SCORING_PROMPT_JSON.replace("{jd_text}", jd).replace("{resume_text}", resume_text)    
    plan_raw = chat_completion(plan_prompt)
    plan = safe_load_json(plan_raw) or {"section_updates": []}
    
    logger.info(f"[SCORING PLAN] Received {len(plan.get('section_updates', []))} section updates")
    for update in plan.get("section_updates", []):
        section_name = update.get("section", "Unknown")
        logger.info(f"[SCORING PLAN] - Section: {section_name}")
    
    jd_hints = chat_completion(JD_HINTS_PROMPT.format(jd_text=jd))

    # Apply plan
    rewritten: Dict[str, str] = {}
    updates = plan.get("section_updates", [])

    # Process Summary section
    if sections.get("Summary"):
        summary_edits = [e for e in updates if normalize_section_name(e.get("section")) == "summary"]
        logger.info(f"[SUMMARY] Found {len(summary_edits)} summary edits from scoring plan")
        
        if mode == "complete_jd":
            logger.info("[SUMMARY] Using GENERATE_FROM_JD_PROMPT (complete_jd mode)")
            send_progress(request_id, 40, "Generating summary...", db)
            prompt = GENERATE_FROM_JD_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Summary"],
                section_edits_json=json.dumps(summary_edits, ensure_ascii=False) if summary_edits else "[]"
            )
        else:
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
        skills_edits = [e for e in updates if normalize_section_name(e.get("section")) == "skills"]
        logger.info(f"[SKILLS] Found {len(skills_edits)} skills edits from scoring plan")
        
        if mode == "complete_jd":
            logger.info("[SKILLS] Using GENERATE_FROM_JD_PROMPT (complete_jd mode)")
            prompt = GENERATE_FROM_JD_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Skills"],
                section_edits_json=json.dumps(skills_edits, ensure_ascii=False) if skills_edits else "[]"
            )
        else:
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
        experience_edits = [e for e in updates if normalize_section_name(e.get("section")) == "experience"]
        logger.info(f"[EXPERIENCE] Found {len(experience_edits)} experience edits from scoring plan")
        
        if mode == "complete_jd":
            logger.info("[EXPERIENCE] Using GENERATE_FROM_JD_PROMPT (complete_jd mode)")
            prompt = GENERATE_FROM_JD_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Experience"],
                section_edits_json=json.dumps(experience_edits, ensure_ascii=False) if experience_edits else "[]"
            )
        else:
            logger.info("[EXPERIENCE] Using APPLY_EDITS_PROMPT (resume_jd mode)")
            prompt = APPLY_EDITS_PROMPT.format(
                jd_hints=jd_hints,
                section_text=sections["Experience"],
                section_edits_json=json.dumps(experience_edits, ensure_ascii=False) if experience_edits else "[]"
            )
        rewritten["Experience"] = chat_completion(prompt).strip()
        logger.info("[EXPERIENCE] Experience section rewritten successfully")

    # Get summary from rewritten into final_json
    if rewritten.get("Summary"):
        final_json["summary"] = rewritten["Summary"]

    # Process Experience
    if rewritten.get("Experience"):
        experience_json = parse_experience_to_json(rewritten["Experience"])
        logger.info(f"[EXPERIENCE] Parsed experience JSON: {experience_json}")

        new_experience_json = balance_experience_roles(experience_json, jd_hints)
        logger.info("[EXPERIENCE] Balanced experience JSON")

        final_json["experience"] = new_experience_json

    # Process Skills
    if rewritten.get("Skills"):
        skills_json = parse_skills_to_json(rewritten["Skills"])
        logger.info(f"[SKILLS] Parsed skills JSON: {skills_json}")
        
        prompt = ORGANIZE_SKILLS_PROMPT.format(skills_json=json.dumps(skills_json, ensure_ascii=False, indent=2))
        response = chat_completion(prompt)

        organized_skills = extract_json(response)
        logger.info(f"[SKILLS] Organized skills JSON: {organized_skills}")
        final_json["technical_skills"] = organized_skills
    else:
        logger.warning("[SKILLS] No Skills section in rewritten content, using original")
        final_json["technical_skills"] = resume_json.get("technical_skills", {})

    send_progress(request_id, 95, "Finalizing resume...", db)
    send_progress(request_id, 100, "Resume completed!", db)
    logger.info(f"[COMPLETE] Resume processing finished successfully")

    return final_json
