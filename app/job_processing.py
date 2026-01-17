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
    GENERATE_EXPERIENCE_FROM_JD_PROMPT, GENERATE_EXPERIENCE_BULLETS_FROM_RESUME_PROMPT, experience_response_schema,
    GENERATE_TECHNICAL_SKILLS_FROM_JD, skills_response_schema,
    SCORING_PROMPT_JSON, APPLY_EDITS_PROMPT,
    ORGANIZE_SKILLS_PROMPT, GENERATE_FROM_JD_PROMPT,
)
from app.helpers import (
    save_debug_file, balance_experience_roles,
    safe_load_json, normalize_section_name,
    convert_resume_json_to_text, extract_json
)
from app.jd_preprocessing import (
    preprocess_jd, get_jd_summary, validate_preprocessed_jd
)
from app.logging_config import (
    setup_detailed_logging, log_section_header, log_subsection, 
    log_data, log_comparison
)

logger = logging.getLogger(__name__)

# Global dict to track job progress in memory
job_progress = {}

# Global dict to store intermediate state for human feedback
intermediate_state = {}


def save_intermediate_state(request_id: str, jd_hints: dict, preprocessed_jd: dict, 
                           resume_json: dict, mode: str, company_name: str, 
                           job_title: str, jd: str) -> dict:
    """Save intermediate state after JD extraction for human feedback
    
    Args:
        request_id: The job request ID
        jd_hints: Extracted JD hints (keywords, skills, phrases)
        preprocessed_jd: Preprocessed job description data
        resume_json: Original resume data
        mode: Processing mode (complete_jd or resume_jd)
        company_name: Company name from job posting
        job_title: Job title from posting
        jd: Original job description text
        
    Returns:
        dict: State object to return to user for feedback
    """
    state = {
        "request_id": request_id,
        "jd_hints": jd_hints,
        "preprocessed_jd": preprocessed_jd,
        "resume_json": resume_json,
        "mode": mode,
        "company_name": company_name,
        "job_title": job_title,
        "jd": jd,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # CRITICAL MODE TRACE
    logger.info(f"[MODE_TRACE] ===== SAVING INTERMEDIATE STATE =====")
    logger.info(f"[MODE_TRACE] Request ID: {request_id}")
    logger.info(f"[MODE_TRACE] Mode being saved: '{mode}'")
    
    # Store in memory for quick access
    intermediate_state[request_id] = state
    
    # Also save to file for persistence
    save_debug_file(
        content=json.dumps(state, indent=2, ensure_ascii=False),
        filename=f"{request_id}_intermediate_state.json",
        prefix="feedback"
    )
    
    logger.info(f"[FEEDBACK] Saved intermediate state for request {request_id}")
    logger.info(f"[FEEDBACK] Mode saved in state: '{mode}'")
    
    # Return user-facing data (exclude internal fields)
    # IMPORTANT: Include mode so frontend can send it back with feedback
    return {
        "request_id": request_id,
        "mode": mode,  # Critical: send mode to frontend
        "technical_keywords": jd_hints.get("technical_keywords", []),
        "soft_skills": jd_hints.get("soft_skills_role_keywords", []),
        "phrases": jd_hints.get("phrases", []),
        "metadata": jd_hints.get("preprocessed_metadata", {}),
        "job_title": job_title,
        "company_name": company_name
    }


def load_intermediate_state(request_id: str, db: Session = None) -> dict:
    """Load intermediate state for resuming after human feedback
    
    Loads from in-memory cache first, then falls back to database.
    This ensures state survives server restarts.
    
    Args:
        request_id: The job request ID
        db: Optional database session for fallback
        
    Returns:
        dict: Complete state object with all data needed to continue
        
    Raises:
        ValueError: If state not found for request_id in both memory and database
    """
    # First try in-memory cache (fastest)
    if request_id in intermediate_state:
        state = intermediate_state[request_id]
        logger.info(f"[FEEDBACK] Loaded intermediate state from MEMORY for request {request_id}")
        logger.info(f"[MODE_TRACE] Mode in memory state: '{state.get('mode', 'NOT_SET')}'")
        return state
    
    # Fallback to database
    logger.warning(f"[FEEDBACK] State not in memory for {request_id}, trying database fallback...")
    
    if db:
        job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id).first()
        if job and job.intermediate_state:
            state = job.intermediate_state
            
            # Ensure mode is set correctly from database record as source of truth
            if job.mode and state.get("mode") != job.mode:
                logger.warning(f"[MODE_TRACE] Mode mismatch! DB: '{job.mode}', State: '{state.get('mode')}' - Using DB value")
                state["mode"] = job.mode
            
            # Re-cache in memory for future access
            intermediate_state[request_id] = state
            logger.info(f"[FEEDBACK] Loaded intermediate state from DATABASE for request {request_id}")
            logger.info(f"[MODE_TRACE] Mode loaded from DB: '{state.get('mode', 'NOT_SET')}'")
            return state
        elif job:
            # Job exists but intermediate_state is empty/null - reconstruct from job record
            logger.warning(f"[FEEDBACK] Job found but intermediate_state is empty, reconstructing from job record")
            state = {
                "request_id": request_id,
                "resume_json": job.resume_input_json or {},
                "jd": job.jd_text or "",
                "company_name": job.company_name,
                "job_title": job.job_title,
                "mode": job.mode or "complete_jd",
                "jd_hints": {},  # Will need to be regenerated or loaded from elsewhere
                "preprocessed_jd": {}
            }
            intermediate_state[request_id] = state
            logger.info(f"[MODE_TRACE] Mode reconstructed from job record: '{state['mode']}'")
            return state
    
    logger.error(f"[FEEDBACK] No intermediate state found for request {request_id} in memory or database")
    raise ValueError(f"No pending job found for request_id: {request_id}. Session may have expired.")


def update_jd_hints_from_feedback(request_id: str, feedback: dict, db: Session = None) -> dict:
    """Update JD hints based on user feedback
    
    Args:
        request_id: The job request ID
        feedback: User's edited keywords/skills/phrases
        db: Optional database session for state fallback
        
    Returns:
        dict: Updated jd_hints object
        
    Raises:
        ValueError: If state not found or feedback invalid
    """
    state = load_intermediate_state(request_id, db)
    
    # Update jd_hints with user feedback
    jd_hints = state["jd_hints"].copy()
    
    if "technical_keywords" in feedback:
        jd_hints["technical_keywords"] = feedback["technical_keywords"]
        logger.info(f"[FEEDBACK] Updated technical_keywords: {len(feedback['technical_keywords'])} items")
    
    if "soft_skills" in feedback:
        jd_hints["soft_skills_role_keywords"] = feedback["soft_skills"]
        logger.info(f"[FEEDBACK] Updated soft_skills: {len(feedback['soft_skills'])} items")
    
    if "phrases" in feedback:
        jd_hints["phrases"] = feedback["phrases"]
        logger.info(f"[FEEDBACK] Updated phrases: {len(feedback['phrases'])} items")
    
    # Update state with modified hints
    state["jd_hints"] = jd_hints
    intermediate_state[request_id] = state
    
    # Save updated state
    save_debug_file(
        content=json.dumps(state, indent=2, ensure_ascii=False),
        filename=f"{request_id}_intermediate_state_updated.json",
        prefix="feedback"
    )
    
    return jd_hints


def cleanup_expired_intermediate_states(ttl_hours: int = 2):
    """Clean up expired intermediate states from memory
    
    Args:
        ttl_hours: Time-to-live in hours (default: 2)
    """
    from datetime import timedelta
    
    cutoff_time = datetime.utcnow() - timedelta(hours=ttl_hours)
    expired_keys = []
    
    for request_id, state in intermediate_state.items():
        state_time_str = state.get("timestamp")
        if state_time_str:
            try:
                state_time = datetime.fromisoformat(state_time_str)
                if state_time < cutoff_time:
                    expired_keys.append(request_id)
            except (ValueError, TypeError):
                # If we can't parse the timestamp, consider it expired
                expired_keys.append(request_id)
    
    # Remove expired states
    for key in expired_keys:
        del intermediate_state[key]
        logger.info(f"[CLEANUP] Removed expired intermediate state: {key}")
    
    if expired_keys:
        logger.info(f"[CLEANUP] Cleaned up {len(expired_keys)} expired intermediate states")
    
    return len(expired_keys)


def send_progress(request_id: str, progress: int, status_message: str, db: Session = None, status: str = None):
    """Update job progress in database and memory
    
    Args:
        request_id: The job request ID
        progress: Progress percentage (0-100)
        status_message: Descriptive message about current step
        db: Database session
        status: Optional status override (e.g., 'awaiting_feedback')
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
                # Use custom status if provided, otherwise determine from progress
                if status:
                    job.status = status
                else:
                    job.status = "processing" if progress < 100 else "completed"
                if progress == 100:
                    job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update job progress: {str(e)}")


async def extract_jd_keywords(data: dict, request_id: str = None, db: Session = None) -> dict:
    """
    PHASE 1: Extract JD keywords and return for human feedback.
    
    This function performs JD preprocessing and keyword extraction, then pauses
    for human review/editing before continuing with content generation.
    
    Flow:
    1. Preprocess job description
    2. Extract keywords, skills, phrases using LLM
    3. Return extracted data for user approval/editing
    
    Returns:
        dict: Extracted keywords for user review with request_id
    """
    # Setup detailed logging for this request
    debug_log, summary_log = setup_detailed_logging(request_id)
    logger.info(f"📝 Detailed logs created:")
    logger.info(f"   Debug log: {debug_log}")
    logger.info(f"   Summary log: {summary_log}")
    
    log_section_header(logger, f"JD KEYWORD EXTRACTION - Request ID: {request_id}")
    
    send_progress(request_id, 5, "Starting JD analysis...", db)
    
    resume_json = data.get("resume_data", {})
    mode = data.get("mode", "complete_jd")
    
    # CRITICAL MODE TRACE - Log at every stage
    logger.info(f"[MODE_TRACE] ===== EXTRACT_JD_KEYWORDS START =====")
    logger.info(f"[MODE_TRACE] Request ID: {request_id}")
    logger.info(f"[MODE_TRACE] Mode from input data: '{mode}'")
    logger.info(f"[MODE_TRACE] Mode default fallback: 'complete_jd'")
    
    # Log request metadata
    log_subsection(logger, "REQUEST METADATA")
    logger.info(f"Processing Mode: {mode}")
    logger.info(f"Request ID: {request_id}")
    
    # Extract job description - handle both old and new payload formats
    if "job_description_data" in data:
        job_json = data.get("job_description_data", {})
        jd = job_json.get("job_description", "")
        company_name = job_json.get("company_name", "")
        job_title = job_json.get("job_title", "")
    else:
        jd = data.get("jd", "")
        company_name = data.get("company_name", "")
        job_title = data.get("job_title", "")
    
    logger.info(f"Company: {company_name}")
    logger.info(f"Job Title: {job_title}")
    logger.info(f"JD Length (raw): {len(jd)} chars")
    
    # Clean job description to remove extra spaces and special characters
    jd = clean_job_description(jd)
    logger.info(f"JD Length (cleaned): {len(jd)} chars")

    # STEP 1: Preprocess JD
    send_progress(request_id, 10, "Preprocessing job description...", db)
    
    import time
    preprocess_start = time.time()
    try:
        # Run JD preprocessing pipeline
        preprocessed_jd = await preprocess_jd(
            raw_text=jd,
            job_title=job_title,
            use_llm_extraction=True  # Use LLM for maximum accuracy
        )
        
        # Validate preprocessed JD
        is_valid, error_msg = validate_preprocessed_jd(preprocessed_jd)
        if not is_valid:
            raise ValueError(f"JD preprocessing validation failed: {error_msg}")
        
        # Log preprocessing summary
        logger.info(f"\n{get_jd_summary(preprocessed_jd)}")
        
        preprocess_duration = time.time() - preprocess_start
        logger.info(f"[PERF] JD preprocessing took {preprocess_duration:.2f}s")
        
    except Exception as e:
        logger.error(f"[JD_PREPROCESSING] Error: {str(e)}")
        raise Exception(f"Failed to preprocess job description: {str(e)}")
    
    # STEP 2: Extract JD hints using preprocessed text
    send_progress(request_id, 15, "Extracting keywords and phrases...", db)
    
    jd_start = time.time()
    try:
        # Use normalized JD text for LLM analysis (cleaner, structured)
        jd_text_for_llm = preprocessed_jd["normalized_jd"]
        
        jd_hints_raw = await chat_completion_async(
            JD_HINTS_PROMPT.format(jd_text=jd_text_for_llm),
            response_schema=jd_hints_response_schema,
            timeout=90  # 90 seconds timeout for JD analysis
        )
        jd_hints = json.loads(jd_hints_raw)
        
        # Rename soft_skills to soft_skills_role_keywords for consistency
        if "soft_skills" in jd_hints:
            jd_hints["soft_skills_role_keywords"] = jd_hints.pop("soft_skills")
        
        # Enrich jd_hints with preprocessing metadata
        jd_hints["preprocessed_metadata"] = preprocessed_jd["metadata"]
        jd_hints["section_weights"] = preprocessed_jd["section_weights"]
        
        jd_duration = time.time() - jd_start
        logger.info(f"[PERF] JD analysis took {jd_duration:.2f}s - extracted {len(jd_hints.get('technical_keywords', []))} keywords")
    except asyncio.TimeoutError:
        logger.error(f"[JD_HINTS] Timeout after 90 seconds")
        raise Exception("Job description analysis timed out. Please try again.")
    except Exception as e:
        logger.error(f"[JD_HINTS] Error: {str(e)}")
        raise Exception(f"Failed to analyze job description: {str(e)}")
    
    # Log JD hints extraction result
    log_subsection(logger, "JD ANALYSIS RESULTS")
    logger.info(f"Technical Keywords: {len(jd_hints.get('technical_keywords', []))} found")
    log_data(logger, "Technical Keywords", jd_hints.get('technical_keywords', [])[:20], max_length=500)
    logger.info(f"Soft Skills: {len(jd_hints.get('soft_skills_role_keywords', []))} found")
    log_data(logger, "Soft Skills", jd_hints.get('soft_skills_role_keywords', [])[:10], max_length=300)
    logger.info(f"Key Phrases: {len(jd_hints.get('phrases', []))} found")
    
    # STEP 3: Save intermediate state and return for feedback
    send_progress(request_id, 25, "Keywords extracted. Awaiting your review...", db, status="awaiting_feedback")
    
    feedback_data = save_intermediate_state(
        request_id=request_id,
        jd_hints=jd_hints,
        preprocessed_jd=preprocessed_jd,
        resume_json=resume_json,
        mode=mode,
        company_name=company_name,
        job_title=job_title,
        jd=jd
    )
    
    log_section_header(logger, "KEYWORD EXTRACTION COMPLETE - AWAITING FEEDBACK")
    logger.info(f"📊 Extracted data ready for user review")
    logger.info(f"📝 Request ID: {request_id}")
    logger.info(f"⏸️  Process paused for human feedback")
    
    return feedback_data


async def generate_resume_content(request_id: str, feedback: dict = None, db: Session = None, mode: str = None) -> dict:
    """
    PHASE 2: Generate resume content after user approves/edits keywords.
    
    This function resumes processing after human feedback, using the approved
    keywords to generate optimized resume content in parallel.
    
    Flow:
    1. Load intermediate state
    2. Apply user feedback (if any)
    3. Generate summary, experience, skills in parallel
    4. Combine results into final resume JSON
    
    Args:
        request_id: The job request ID
        feedback: Optional user edits to keywords/skills/phrases
        db: Database session
        mode: Processing mode from payload (priority), falls back to DB if not provided
        
    Returns:
        dict: Complete optimized resume JSON
    """
    log_section_header(logger, f"RESUME CONTENT GENERATION - Request ID: {request_id}")
    
    send_progress(request_id, 30, "Resuming with approved keywords...", db, status="processing")
    
    # Load intermediate state (with database fallback)
    try:
        state = load_intermediate_state(request_id, db)
    except ValueError as e:
        logger.error(f"[GENERATION] {str(e)}")
        raise
    
    # Log mode at start of generation
    logger.info(f"[MODE_TRACE] ===== GENERATION PHASE START =====")
    logger.info(f"[MODE_TRACE] Request ID: {request_id}")
    logger.info(f"[MODE_TRACE] Mode from state: '{state.get('mode', 'NOT_SET')}'")
    
    # Apply user feedback if provided
    if feedback:
        logger.info(f"[FEEDBACK] Applying user edits to keywords")
        jd_hints = update_jd_hints_from_feedback(request_id, feedback, db)
    else:
        logger.info(f"[FEEDBACK] No edits provided, using original extraction")
        jd_hints = state["jd_hints"]
    
    # Extract state variables with safe defaults
    resume_json = state.get("resume_json", {})
    preprocessed_jd = state.get("preprocessed_jd", {})
    
    # MODE RESOLUTION: Payload > Database > State > Default
    # Priority 1: Use mode from payload if provided
    if mode:
        logger.info(f"[MODE] Using mode from PAYLOAD: '{mode}'")
    else:
        # Priority 2: Fallback to database job record
        if db:
            try:
                job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id).first()
                if job and job.mode:
                    mode = job.mode
                    logger.info(f"[MODE] Using mode from DATABASE: '{mode}'")
            except Exception as e:
                logger.warning(f"[MODE] Failed to load mode from DB: {str(e)}")
        
        # Priority 3: Fallback to state (for backward compatibility)
        if not mode:
            mode = state.get("mode", "complete_jd")
            logger.info(f"[MODE] Using mode from STATE/DEFAULT: '{mode}'")
    
    # DEBUG LOGGING: Critical for tracking mode issues
    logger.info(f"[MODE DEBUG] ========================================")
    logger.info(f"[MODE DEBUG] Request ID: {request_id}")
    logger.info(f"[MODE DEBUG] Final resolved mode: '{mode}'")
    logger.info(f"[MODE DEBUG] State keys present: {list(state.keys())}")
    logger.info(f"[MODE DEBUG] ========================================")
    
    # Log input resume data
    log_subsection(logger, "INPUT RESUME DATA")
    log_data(logger, "Name", resume_json.get("name", ""))
    log_data(logger, "Summary", resume_json.get("summary", ""), max_length=300)
    log_data(logger, "Technical Skills", resume_json.get("technical_skills", {}), max_length=400)
    
    input_experience = resume_json.get("experience", [])
    logger.info(f"Experience: {len(input_experience)} roles")
    for idx, exp in enumerate(input_experience[:3]):  # Log first 3 roles
        logger.info(f"  Role {idx+1}: {exp.get('company', '')} - {exp.get('role', '')} ({exp.get('period', '')})")
        logger.info(f"          {len(exp.get('points', exp.get('bullets', [])))} bullet points")

    # Prepare final JSON with static fields
    final_json = {
        "name": resume_json.get("name", ""),
        "contact": resume_json.get("contact", ""),
        "education": resume_json.get("education", [])
    }
    
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
    
    log_section_header(logger, f"PARALLEL PROCESSING - Mode: {mode.upper()}")
    
    send_progress(request_id, 35, "Generating optimized content...", db)
    
    # Generate summary, experience, skills in PARALLEL (same as before)
    async def generate_summary():
        """Generate optimized summary from JD hints - SAME FOR BOTH MODES"""
        try:
            original_summary = resume_json.get("summary", "")
            
            # Always generate new summary using JD (regardless of mode)
            log_subsection(logger, "SUMMARY GENERATION")
            logger.info("✓ Generating summary from JD hints (applies to both modes)")
            
            # Always use complete_jd logic
            prompt = GENERATE_SUMMARY_FROM_JD_PROMPT.format(
                technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                soft_skills=json.dumps(jd_hints.get("soft_skills_role_keywords", []), ensure_ascii=False),
                phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                original_summary=original_summary
            )
            
            logger.info(f"[SUMMARY] Using GENERATE_SUMMARY_FROM_JD_PROMPT")
            result_raw = await asyncio.wait_for(
                chat_completion_async(prompt, response_schema=summary_response_schema),
                timeout=60
            )
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
            
            # Extract additional context from preprocessing metadata
            preprocessed_metadata = jd_hints.get("preprocessed_metadata", {})
            role_title = preprocessed_metadata.get("title", "Not specified")
            role_seniority = preprocessed_metadata.get("seniority", "Not specified")
            
            # Extract requirements from preprocessed JD sections
            preprocessed_sections = preprocessed_jd.get("sections", {})
            jd_requirements = preprocessed_sections.get("requirements", [])
            
            logger.info(f"[EXPERIENCE] Role: {role_title}, Seniority: {role_seniority}, Requirements: {len(jd_requirements)}")
            
            # Use different prompts based on mode
            if mode == "complete_jd":
                logger.info("[EXPERIENCE] Using GENERATE_EXPERIENCE_FROM_JD_PROMPT (complete_jd mode)")
                
                # Extract only company, role, period (no bullets) for complete_jd mode
                experience_metadata = []
                for exp in experience_data:
                    experience_metadata.append({
                        "company": exp.get("company", ""),
                        "role": exp.get("role", ""),
                        "period": exp.get("period", "")
                    })
                
                logger.info(f"[EXPERIENCE] Sending metadata only (no bullets) for {len(experience_metadata)} roles")
                
                prompt = GENERATE_EXPERIENCE_FROM_JD_PROMPT.format(
                    technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                    soft_skills=json.dumps(jd_hints.get("soft_skills_role_keywords", []), ensure_ascii=False),
                    phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                    experience_data=json.dumps(experience_metadata, ensure_ascii=False, indent=2),
                    jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                    role_seniority=role_seniority,
                    role_title=role_title
                )
            else:  # resume_jd mode
                logger.info("[EXPERIENCE] Using GENERATE_EXPERIENCE_BULLETS_FROM_RESUME_PROMPT (resume_jd mode)")
                logger.info(f"[EXPERIENCE] Enhancing existing bullets for {len(experience_data)} roles")
                
                # In resume_jd mode, send complete experience with all bullets for enhancement
                prompt = GENERATE_EXPERIENCE_BULLETS_FROM_RESUME_PROMPT.format(
                    technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                    soft_skills=json.dumps(jd_hints.get("soft_skills_role_keywords", []), ensure_ascii=False),
                    phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                    experience_data=json.dumps(experience_data, ensure_ascii=False, indent=2),
                    jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                    role_seniority=role_seniority,
                    role_title=role_title
                )
            
            result_raw = await chat_completion_async(prompt, response_schema=experience_response_schema, timeout=90)
            result = json.loads(result_raw)
            experience_result = result.get("experience", [])
            
            # Validate: Check if we got all experience entries back
            input_exp_count = len(experience_data)
            output_exp_count = len(experience_result)
            if output_exp_count < input_exp_count:
                logger.warning(f"[EXPERIENCE] ⚠️ MISSING ENTRIES: Input had {input_exp_count} roles, but LLM returned only {output_exp_count} roles")
                logger.warning(f"[EXPERIENCE] Input companies: {[exp.get('company', 'N/A') for exp in experience_data]}")
                logger.warning(f"[EXPERIENCE] Output companies: {[exp.get('company', 'N/A') for exp in experience_result]}")
                logger.warning(f"[EXPERIENCE] This may be due to LLM output token limits. Response length: {len(result_raw)} chars")
            
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
        """Generate technical skills categorized by JD requirements - SAME FOR BOTH MODES"""
        try:
            existing_skills = resume_json.get("technical_skills", {})
            
            # Always generate new skills using JD (regardless of mode)
            log_subsection(logger, "SKILLS GENERATION")
            logger.info("✓ Generating skills from JD hints (applies to both modes)")
            
            # Always use complete_jd logic
            prompt = GENERATE_TECHNICAL_SKILLS_FROM_JD.format(
                jd_technical_keywords=", ".join(jd_hints.get("technical_keywords", [])),
                existing_skills=json.dumps(existing_skills, ensure_ascii=False, indent=2)
            )
            
            logger.info(f"[SKILLS] Using GENERATE_TECHNICAL_SKILLS_FROM_JD")
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
    send_progress(request_id, 50, "Generating summary, experience, and skills...", db)
    
    summary, experience, skills = await asyncio.gather(
        generate_summary(),
        generate_experience(),
        generate_skills()
    )
    
    send_progress(request_id, 90, "Parallel optimization complete. Finalizing...", db)
    
    # Combine results into final JSON
    final_json["summary"] = summary
    final_json["experience"] = experience
    final_json["technical_skills"] = skills
    
    # Log final output comparison
    log_section_header(logger, "FINAL OUTPUT COMPARISON")
    
    if mode == "resume_jd":
        logger.info("🔍 RESUME_JD MODE - Enhanced content with JD keywords:")
        logger.info("")
        logger.info(f"✓ Summary: Generated from JD (ATS-optimized)")
        logger.info(f"✓ Skills: Generated from JD (ATS-optimized)")
        logger.info(f"✓ Experience: Enhanced existing bullets with JD keywords")
        logger.info(f"   - Input: {len(resume_json.get('experience', []))} roles")
        logger.info(f"   - Output: {len(final_json['experience'])} roles")
    else:
        logger.info("🔍 COMPLETE_JD MODE - Generated fresh content from JD:")
        log_data(logger, "Generated Summary", final_json['summary'], max_length=300)
        logger.info(f"Generated Experience: {len(final_json['experience'])} roles")
        logger.info(f"Generated Skills: {len(final_json['technical_skills'])} categories")
    
    send_progress(request_id, 100, "Resume completed!", db)
    log_section_header(logger, "PROCESSING COMPLETE ✅")
    logger.info(f"📊 Final resume JSON has {len(final_json)} top-level fields")
    
    # Clean up intermediate state
    if request_id in intermediate_state:
        del intermediate_state[request_id]
        logger.info(f"[CLEANUP] Removed intermediate state for request {request_id}")
    
    return final_json


async def process_resume_parallel(data: dict, request_id: str = None, db: Session = None) -> dict:
    """
    LEGACY: Process resume with parallel API calls (without human feedback).
    
    This function is kept for backward compatibility. For new implementations,
    use the two-phase approach:
    1. extract_jd_keywords() - returns for feedback
    2. generate_resume_content() - continues after approval
    
    Flow:
    1. Extract JD hints (sequential - required for other steps)
    2. Generate summary, experience, skills in parallel
    3. Combine results into final resume JSON
    
    Expected time savings: 40-50% (14-23s → 8-13s)
    """
    logger.info("[LEGACY] Using process_resume_parallel without human feedback")
    logger.warning("⚠️ Using legacy process_resume_parallel - consider migrating to two-phase flow")
    logger.info("   Phase 1: extract_jd_keywords() - returns for user review")
    logger.info("   Phase 2: generate_resume_content() - continues after approval")
    
    # Setup detailed logging for this request
    debug_log, summary_log = setup_detailed_logging(request_id)
    logger.info(f"📝 Detailed logs created:")
    logger.info(f"   Debug log: {debug_log}")
    logger.info(f"   Summary log: {summary_log}")
    
    log_section_header(logger, f"RESUME PROCESSING START (LEGACY) - Request ID: {request_id}")
    
    send_progress(request_id, 5, "Starting resume processing...", db)
    
    resume_json = data.get("resume_data", {})
    mode = data.get("mode", "complete_jd")
    
    # Log request metadata
    log_subsection(logger, "REQUEST METADATA")
    logger.info(f"Processing Mode: {mode}")
    logger.info(f"Request ID: {request_id}")
    
    # Extract job description - handle both old and new payload formats
    if "job_description_data" in data:
        job_json = data.get("job_description_data", {})
        jd = job_json.get("job_description", "")
        company_name = job_json.get("company_name", "")
        job_title = job_json.get("job_title", "")
    else:
        jd = data.get("jd", "")
        company_name = data.get("company_name", "")
        job_title = data.get("job_title", "")
    
    logger.info(f"Company: {company_name}")
    logger.info(f"Job Title: {job_title}")
    logger.info(f"JD Length (raw): {len(jd)} chars")
    
    # Clean job description to remove extra spaces and special characters
    jd = clean_job_description(jd)
    logger.info(f"JD Length (cleaned): {len(jd)} chars")
    
    # Log input resume data
    log_subsection(logger, "INPUT RESUME DATA")
    log_data(logger, "Name", resume_json.get("name", ""))
    log_data(logger, "Summary", resume_json.get("summary", ""), max_length=300)
    log_data(logger, "Technical Skills", resume_json.get("technical_skills", {}), max_length=400)
    
    input_experience = resume_json.get("experience", [])
    logger.info(f"Experience: {len(input_experience)} roles")
    for idx, exp in enumerate(input_experience[:3]):  # Log first 3 roles
        logger.info(f"  Role {idx+1}: {exp.get('company', '')} - {exp.get('role', '')} ({exp.get('period', '')})")
        logger.info(f"          {len(exp.get('points', exp.get('bullets', [])))} bullet points")

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

    # STEP 1: Preprocess JD (new comprehensive preprocessing layer)
    send_progress(request_id, 10, "Preprocessing job description...", db)
    
    import time
    preprocess_start = time.time()
    try:
        # Run JD preprocessing pipeline
        preprocessed_jd = await preprocess_jd(
            raw_text=jd,
            job_title=job_title,
            use_llm_extraction=True  # Use LLM for maximum accuracy
        )
        
        # Validate preprocessed JD
        is_valid, error_msg = validate_preprocessed_jd(preprocessed_jd)
        if not is_valid:
            raise ValueError(f"JD preprocessing validation failed: {error_msg}")
        
        # Log preprocessing summary
        logger.info(f"\n{get_jd_summary(preprocessed_jd)}")
        
        # # Save preprocessed JD for debugging
        # save_debug_file(
        #     content=json.dumps(preprocessed_jd, indent=2),
        #     filename=f"{request_id}_preprocessed_jd.json",
        #     prefix="jd_preprocessing"
        # )
        
        preprocess_duration = time.time() - preprocess_start
        logger.info(f"[PERF] JD preprocessing took {preprocess_duration:.2f}s")
        
    except Exception as e:
        logger.error(f"[JD_PREPROCESSING] Error: {str(e)}")
        raise Exception(f"Failed to preprocess job description: {str(e)}")
    
    # STEP 2: Extract JD hints using preprocessed text (SEQUENTIAL - required first)
    send_progress(request_id, 15, "Analyzing job description...", db)
    
    jd_start = time.time()
    try:
        # Use normalized JD text for LLM analysis (cleaner, structured)
        jd_text_for_llm = preprocessed_jd["normalized_jd"]
        
        jd_hints_raw = await chat_completion_async(
            JD_HINTS_PROMPT.format(jd_text=jd_text_for_llm),
            response_schema=jd_hints_response_schema,
            timeout=90  # 90 seconds timeout for JD analysis
        )
        jd_hints = json.loads(jd_hints_raw)
        
        # Rename soft_skills to soft_skills_role_keywords for consistency
        if "soft_skills" in jd_hints:
            jd_hints["soft_skills_role_keywords"] = jd_hints.pop("soft_skills")
        
        # Enrich jd_hints with preprocessing metadata
        jd_hints["preprocessed_metadata"] = preprocessed_jd["metadata"]
        jd_hints["section_weights"] = preprocessed_jd["section_weights"]
        
        jd_duration = time.time() - jd_start
        logger.info(f"[PERF] JD analysis took {jd_duration:.2f}s - extracted {len(jd_hints.get('technical_keywords', []))} keywords")
    except asyncio.TimeoutError:
        logger.error(f"[JD_HINTS] Timeout after 90 seconds")
        raise Exception("Job description analysis timed out. Please try again.")
    except Exception as e:
        logger.error(f"[JD_HINTS] Error: {str(e)}")
        raise Exception(f"Failed to analyze job description: {str(e)}")
    
    # Log JD hints extraction result
    log_subsection(logger, "JD ANALYSIS RESULTS")
    logger.info(f"Technical Keywords: {len(jd_hints.get('technical_keywords', []))} found")
    log_data(logger, "Technical Keywords", jd_hints.get('technical_keywords', [])[:20], max_length=500)
    logger.info(f"Soft Skills: {len(jd_hints.get('soft_skills_role_keywords', []))} found")
    log_data(logger, "Soft Skills", jd_hints.get('soft_skills_role_keywords', [])[:10], max_length=300)
    logger.info(f"Key Phrases: {len(jd_hints.get('phrases', []))} found")
    
    log_section_header(logger, f"PARALLEL PROCESSING - Mode: {mode.upper()}")
    
    send_progress(request_id, 25, "JD analysis complete. Starting parallel optimization...", db)
    
    # STEP 2: Generate summary, experience, skills in PARALLEL
    async def generate_summary():
        """Generate optimized summary from JD hints - SAME FOR BOTH MODES"""
        try:
            original_summary = resume_json.get("summary", "")
            
            # Always generate new summary using JD (regardless of mode)
            log_subsection(logger, "SUMMARY GENERATION")
            logger.info("✓ Generating summary from JD hints (applies to both modes)")
            
            # Always use complete_jd logic
            prompt = GENERATE_SUMMARY_FROM_JD_PROMPT.format(
                technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                soft_skills=json.dumps(jd_hints.get("soft_skills_role_keywords", []), ensure_ascii=False),
                phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                original_summary=original_summary
            )
            
            logger.info(f"[SUMMARY] Using GENERATE_SUMMARY_FROM_JD_PROMPT")
            result_raw = await asyncio.wait_for(
                chat_completion_async(prompt, response_schema=summary_response_schema),
                timeout=60
            )
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
            
            # Extract additional context from preprocessing metadata
            preprocessed_metadata = jd_hints.get("preprocessed_metadata", {})
            role_title = preprocessed_metadata.get("title", "Not specified")
            role_seniority = preprocessed_metadata.get("seniority", "Not specified")
            
            # Extract requirements from preprocessed JD sections
            preprocessed_sections = preprocessed_jd.get("sections", {})
            jd_requirements = preprocessed_sections.get("requirements", [])
            
            logger.info(f"[EXPERIENCE] Role: {role_title}, Seniority: {role_seniority}, Requirements: {len(jd_requirements)}")
            
            # Use different prompts based on mode
            if mode == "complete_jd":
                logger.info("[EXPERIENCE] Using GENERATE_EXPERIENCE_FROM_JD_PROMPT (complete_jd mode)")
                
                # Extract only company, role, period (no bullets) for complete_jd mode
                experience_metadata = []
                for exp in experience_data:
                    experience_metadata.append({
                        "company": exp.get("company", ""),
                        "role": exp.get("role", ""),
                        "period": exp.get("period", "")
                    })
                
                logger.info(f"[EXPERIENCE] Sending metadata only (no bullets) for {len(experience_metadata)} roles")
                
                prompt = GENERATE_EXPERIENCE_FROM_JD_PROMPT.format(
                    technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                    soft_skills=json.dumps(jd_hints.get("soft_skills_role_keywords", []), ensure_ascii=False),
                    phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                    experience_data=json.dumps(experience_metadata, ensure_ascii=False, indent=2),
                    jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                    role_seniority=role_seniority,
                    role_title=role_title
                )
            else:  # resume_jd mode
                logger.info("[EXPERIENCE] Using GENERATE_EXPERIENCE_BULLETS_FROM_RESUME_PROMPT (resume_jd mode)")
                logger.info(f"[EXPERIENCE] Enhancing existing bullets for {len(experience_data)} roles")
                
                # In resume_jd mode, send complete experience with all bullets for enhancement
                prompt = GENERATE_EXPERIENCE_BULLETS_FROM_RESUME_PROMPT.format(
                    technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                    soft_skills=json.dumps(jd_hints.get("soft_skills_role_keywords", []), ensure_ascii=False),
                    phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                    experience_data=json.dumps(experience_data, ensure_ascii=False, indent=2),
                    jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                    role_seniority=role_seniority,
                    role_title=role_title
                )
            
            result_raw = await chat_completion_async(prompt, response_schema=experience_response_schema, timeout=90)
            result = json.loads(result_raw)
            experience_result = result.get("experience", [])
            
            # Validate: Check if we got all experience entries back
            input_exp_count = len(experience_data)
            output_exp_count = len(experience_result)
            if output_exp_count < input_exp_count:
                logger.warning(f"[EXPERIENCE PARALLEL] ⚠️ MISSING ENTRIES: Input had {input_exp_count} roles, but LLM returned only {output_exp_count} roles")
                logger.warning(f"[EXPERIENCE PARALLEL] Input companies: {[exp.get('company', 'N/A') for exp in experience_data]}")
                logger.warning(f"[EXPERIENCE PARALLEL] Output companies: {[exp.get('company', 'N/A') for exp in experience_result]}")
                logger.warning(f"[EXPERIENCE PARALLEL] This may be due to LLM output token limits. Response length: {len(result_raw)} chars")
            
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
        """Generate technical skills categorized by JD requirements - SAME FOR BOTH MODES"""
        try:
            existing_skills = resume_json.get("technical_skills", {})
            
            # Always generate new skills using JD (regardless of mode)
            log_subsection(logger, "SKILLS GENERATION")
            logger.info("✓ Generating skills from JD hints (applies to both modes)")
            
            # Always use complete_jd logic
            prompt = GENERATE_TECHNICAL_SKILLS_FROM_JD.format(
                jd_technical_keywords=", ".join(jd_hints.get("technical_keywords", [])),
                existing_skills=json.dumps(existing_skills, ensure_ascii=False, indent=2)
            )
            
            logger.info(f"[SKILLS] Using GENERATE_TECHNICAL_SKILLS_FROM_JD")
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
    send_progress(request_id, 30, "Generating new content...", db)
    
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
    
    # Log final output comparison
    log_section_header(logger, "FINAL OUTPUT COMPARISON")
    
    # Log final output
    log_section_header(logger, "FINAL OUTPUT COMPARISON")
    
    if mode == "resume_jd":
        logger.info("🔍 RESUME_JD MODE - Enhanced content with JD keywords:")
        logger.info("")
        logger.info(f"✓ Summary: Generated from JD (ATS-optimized)")
        logger.info(f"✓ Skills: Generated from JD (ATS-optimized)")
        logger.info(f"✓ Experience: Enhanced existing bullets with JD keywords")
        logger.info(f"   - Input: {len(resume_json.get('experience', []))} roles")
        logger.info(f"   - Output: {len(final_json['experience'])} roles")
    else:
        logger.info("🔍 COMPLETE_JD MODE - Generated fresh content from JD:")
        log_data(logger, "Generated Summary", final_json['summary'], max_length=300)
        logger.info(f"Generated Experience: {len(final_json['experience'])} roles")
        logger.info(f"Generated Skills: {len(final_json['technical_skills'])} categories")
    
    send_progress(request_id, 100, "Resume completed!", db)
    log_section_header(logger, "PROCESSING COMPLETE ✅")
    logger.info(f"📊 Final resume JSON has {len(final_json)} top-level fields")
    logger.info(f"📝 Detailed logs saved")
    logger.info(f"   Debug: {debug_log}")
    logger.info(f"   Summary: {summary_log}")
    
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
