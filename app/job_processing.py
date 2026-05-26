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
    clean_job_description, clean_experience_bullets,
    repair_json
)
from app.prompts import (
    JD_HINTS_PROMPT, jd_hints_response_schema,
    CATEGORIZE_KEYWORDS_PROMPT, categorize_keywords_response_schema,
    GENERATE_SUMMARY_FROM_JD_PROMPT, summary_response_schema,
    GENERATE_EXPERIENCE_FROM_JD_PROMPT, GENERATE_EXPERIENCE_BULLETS_FROM_RESUME_PROMPT, experience_response_schema,
    GENERATE_SINGLE_ROLE_EXPERIENCE_PROMPT, ENHANCE_SINGLE_ROLE_EXPERIENCE_PROMPT, single_role_response_schema,
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
    
    # PRIORITY: Use mode from parameter (frontend) - most reliable for parallel requests
    # FALLBACK: Load from state, then database, then default
    VALID_MODES = ["complete_jd", "resume_jd"]
    mode_override = mode  # Store original parameter for fallback logic
    
    if mode_override:
        # Validate mode from frontend
        if mode_override in VALID_MODES:
            mode = mode_override
            logger.info(f"[MODE] Using explicit mode from frontend: '{mode}'")
        else:
            logger.error(f"[MODE] Invalid mode_override '{mode_override}' - will use fallback")
            mode_override = None  # Reset to trigger fallback logic
    
    # Fallback: if mode_override wasn't valid or wasn't provided
    if not mode_override:
        mode = state.get("mode")
        # Validate mode from state
        if mode and mode not in VALID_MODES:
            logger.error(f"[MODE] Invalid mode in state '{mode}' - treating as unset")
            mode = None
            
        if not mode:
            # Final fallback: check database
            if db:
                job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id).first()
                if job and job.mode and job.mode in VALID_MODES:
                    mode = job.mode
                    logger.warning(f"[MODE] Loaded from database fallback: '{mode}'")
                else:
                    mode = "complete_jd"  # Last resort default
                    logger.error(f"[MODE] No valid mode found anywhere! Using default: '{mode}'")
            else:
                mode = "complete_jd"
                logger.error(f"[MODE] No db session, using default: '{mode}'")
        else:
            logger.info(f"[MODE] Loaded from state: '{mode}'")
    
    preprocessed_jd = state.get("preprocessed_jd", {})
    
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
            result_raw = await chat_completion_async(
                prompt, response_schema=summary_response_schema, timeout=90
            )
            result = json.loads(result_raw)
            logger.info("[SUMMARY] Generated successfully")
            return result.get("summary", "")

        except asyncio.TimeoutError:
            logger.error("[SUMMARY] Timeout after 90 seconds")
            return resume_json.get("summary", "")
        except Exception as e:
            logger.error(f"[SUMMARY] Error: {str(e)}")
            return resume_json.get("summary", "")
    
    async def generate_experience():
        """Generate optimized experience bullets from JD hints.
        Uses chunked processing for 3+ experiences to prevent LLM truncation."""
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
            
            # ============================================================
            # CHUNKED PROCESSING: Use single-role prompts for 3+ experiences
            # to prevent LLM output truncation issues
            # ============================================================
            num_experiences = len(experience_data)
            CHUNKING_THRESHOLD = 2  # Use chunking for more than 2 experiences
            
            if mode == "complete_jd" and num_experiences > CHUNKING_THRESHOLD:
                logger.info(f"[EXPERIENCE CHUNKED] Using chunked generation for {num_experiences} roles (threshold: {CHUNKING_THRESHOLD})")
                
                # Get all keywords
                all_technical_keywords = jd_hints.get("technical_keywords", [])
                all_soft_skills = jd_hints.get("soft_skills_role_keywords", [])
                all_phrases = jd_hints.get("phrases", [])
                
                total_keywords = len(all_technical_keywords)
                total_soft_skills = len(all_soft_skills)
                total_phrases = len(all_phrases)
                
                logger.info(f"[EXPERIENCE CHUNKED] Total keywords to distribute: {total_keywords} technical, {total_soft_skills} soft skills, {total_phrases} phrases")
                
                # Calculate keyword allocation percentages per role
                # Most recent: 40-50%, Second: 30-40%, Rest: 10-20%
                keyword_allocations = []
                if num_experiences == 3:
                    keyword_allocations = [45, 35, 20]
                elif num_experiences == 4:
                    keyword_allocations = [40, 30, 20, 10]
                elif num_experiences >= 5:
                    keyword_allocations = [40, 25]
                    remaining = 35
                    for _ in range(num_experiences - 2):
                        keyword_allocations.append(remaining // (num_experiences - 2))
                
                # ============================================================
                # LLM-BASED KEYWORD CATEGORIZATION
                # Ask LLM to intelligently identify core vs supplementary keywords
                # Also handles supplementation when keywords are insufficient
                # ============================================================
                
                # Get user's existing skills from resume for supplementation context
                existing_skills = resume_json.get("technical_skills", {})
                if isinstance(existing_skills, dict):
                    # Flatten skills dict to list
                    existing_skills_list = []
                    for category, skills in existing_skills.items():
                        if isinstance(skills, list):
                            existing_skills_list.extend(skills)
                        elif isinstance(skills, str):
                            existing_skills_list.append(skills)
                    existing_skills = existing_skills_list
                elif not isinstance(existing_skills, list):
                    existing_skills = []
                
                # Get job title/domain for supplementation context
                job_domain = preprocessed_jd.get("metadata", {}).get("job_title", "Software Engineer")
                
                # Call LLM to categorize keywords intelligently (with competing tech resolution)
                _jd_preferred = preprocessed_sections.get("preferred", preprocessed_sections.get("nice_to_have", []))
                _jd_req_text = " ".join(jd_requirements[:10]) if isinstance(jd_requirements, list) else str(jd_requirements)[:600]
                _jd_pref_text = " ".join(_jd_preferred[:5]) if isinstance(_jd_preferred, list) else str(_jd_preferred)[:400]

                try:
                    logger.info(f"[EXPERIENCE CHUNKED] Calling LLM to categorize {total_keywords} keywords...")

                    categorization_prompt = CATEGORIZE_KEYWORDS_PROMPT.format(
                        job_domain=job_domain,
                        num_roles=num_experiences,
                        jd_requirements_text=_jd_req_text[:600],
                        jd_preferred_text=_jd_pref_text[:400],
                        technical_keywords=json.dumps(all_technical_keywords, ensure_ascii=False),
                        existing_skills=json.dumps(existing_skills[:20], ensure_ascii=False)
                    )

                    categorization_result_raw = await chat_completion_async(
                        categorization_prompt,
                        response_schema=categorize_keywords_response_schema,
                        timeout=45
                    )
                    categorization_result_repaired = repair_json(categorization_result_raw)
                    categorization = json.loads(categorization_result_repaired)

                    # Log competing technology prioritization decisions
                    competing_groups = categorization.get("competing_groups", [])
                    if competing_groups:
                        for grp in competing_groups:
                            logger.info(f"[COMPETING TECH] {grp.get('group_name','?')}: preferred={grp.get('winner','?')}, secondary={grp.get('secondary',[])}, reason={grp.get('reason','')}")

                    # Extract categorized keywords (all tools kept — winners in core, secondary in supplementary)
                    core_technical = categorization.get("core_keywords", [])
                    supplementary_technical = categorization.get("supplementary_keywords", [])
                    supplemented_keywords = categorization.get("supplemented_keywords", [])

                    # Combine supplementary and supplemented for distribution
                    remaining_technical = supplementary_technical + supplemented_keywords

                    logger.info(f"[EXPERIENCE CHUNKED] LLM categorization: {len(core_technical)} core, {len(supplementary_technical)} supplementary, {len(supplemented_keywords)} supplemented")
                    logger.info(f"[EXPERIENCE CHUNKED] Core keywords: {core_technical}")
                    if supplemented_keywords:
                        logger.info(f"[EXPERIENCE CHUNKED] Supplemented keywords: {supplemented_keywords}")

                except Exception as cat_error:
                    logger.warning(f"[EXPERIENCE CHUNKED] LLM categorization failed: {str(cat_error)}. Using positional fallback.")
                    core_tech_count = max(3, total_keywords // 5)
                    core_technical = all_technical_keywords[:core_tech_count]
                    remaining_technical = all_technical_keywords[core_tech_count:]

                # Soft skills and phrases still use positional splitting (simpler categories)
                core_soft_count = max(2, total_soft_skills // 5)
                core_phrase_count = max(2, total_phrases // 5)
                core_soft_skills = all_soft_skills[:core_soft_count]
                core_phrases = all_phrases[:core_phrase_count]
                remaining_soft_skills = all_soft_skills[core_soft_count:]
                remaining_phrases = all_phrases[core_phrase_count:]

                logger.info(f"[EXPERIENCE CHUNKED] Final split - Core: {len(core_technical)} tech, {len(core_soft_skills)} soft, {len(core_phrases)} phrases")
                logger.info(f"[EXPERIENCE CHUNKED] To distribute: {len(remaining_technical)} tech, {len(remaining_soft_skills)} soft, {len(remaining_phrases)} phrases")
                
                # Calculate start/end indices for each role based on allocation percentages
                def split_by_percentages(items, percentages):
                    """Split a list into chunks based on percentage allocations."""
                    chunks = []
                    total = len(items)
                    current_idx = 0
                    
                    for i, pct in enumerate(percentages):
                        # Calculate chunk size
                        if i == len(percentages) - 1:
                            # Last role gets whatever remains
                            chunk_size = total - current_idx
                        else:
                            chunk_size = max(1, int(total * pct / 100))
                        
                        end_idx = min(current_idx + chunk_size, total)
                        chunks.append(items[current_idx:end_idx])
                        current_idx = end_idx
                    
                    return chunks
                
                # Split remaining keywords by role
                tech_chunks = split_by_percentages(remaining_technical, keyword_allocations)
                soft_chunks = split_by_percentages(remaining_soft_skills, keyword_allocations)
                phrase_chunks = split_by_percentages(remaining_phrases, keyword_allocations)
                
                # Bullet counts: more bullets for recent roles
                bullet_counts = []
                for i in range(num_experiences):
                    if i == 0:
                        bullet_counts.append(8)  # Most recent: 8 bullets
                    elif i == 1:
                        bullet_counts.append(7)  # Second: 7 bullets
                    else:
                        bullet_counts.append(6)  # Older: 6 bullets
                
                # Generate experience for each role sequentially
                all_experience_results = []
                for idx, exp in enumerate(experience_data):
                    role_position = idx + 1
                    bullet_count = bullet_counts[idx] if idx < len(bullet_counts) else 6
                    
                    # Combine core keywords + role-specific keywords
                    role_technical = core_technical + (tech_chunks[idx] if idx < len(tech_chunks) else [])
                    role_soft_skills = core_soft_skills + (soft_chunks[idx] if idx < len(soft_chunks) else [])
                    role_phrases = core_phrases + (phrase_chunks[idx] if idx < len(phrase_chunks) else [])
                    
                    logger.info(f"[EXPERIENCE CHUNKED] Generating role {role_position}/{num_experiences}: {exp.get('company', 'Unknown')} - {exp.get('role', 'Unknown')}")
                    logger.info(f"[EXPERIENCE CHUNKED] Role {role_position} keywords: {len(role_technical)} tech, {len(role_soft_skills)} soft, {len(role_phrases)} phrases, {bullet_count} bullets")
                    
                    prompt = GENERATE_SINGLE_ROLE_EXPERIENCE_PROMPT.format(
                        role_position=role_position,
                        total_roles=num_experiences,
                        keyword_allocation=len(role_technical),  # Now passing actual count, not percentage
                        bullet_count=bullet_count,
                        role_seniority=role_seniority,
                        role_title=role_title,
                        technical_keywords=json.dumps(role_technical, ensure_ascii=False),
                        soft_skills=json.dumps(role_soft_skills, ensure_ascii=False),
                        phrases=json.dumps(role_phrases, ensure_ascii=False),
                        jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                        company=exp.get("company", ""),
                        role_name=exp.get("role", ""),
                        period=exp.get("period", "")
                    )
                    
                    try:
                        # Shorter timeout per role since each is simpler
                        result_raw = await chat_completion_async(prompt, response_schema=single_role_response_schema, timeout=60)
                        logger.info(f"[EXPERIENCE CHUNKED] Role {role_position} raw response length: {len(result_raw)} chars")
                        
                        result_raw_repaired = repair_json(result_raw)
                        result = json.loads(result_raw_repaired)
                        
                        # Handle both possible return formats
                        fallback_role = {
                            "company": exp.get("company", ""),
                            "role": exp.get("role", ""),
                            "period": exp.get("period", ""),
                            "points": exp.get("points", exp.get("bullets", []))
                        }
                        if isinstance(result, dict):
                            if "experience" in result and result["experience"]:
                                role_data = result["experience"][0]
                            elif "company" in result or "role" in result or "points" in result:
                                # Direct role object (no wrapping)
                                role_data = result
                            else:
                                # LLM returned empty/wrong structure
                                logger.warning(f"[EXPERIENCE CHUNKED] Role {role_position} returned empty experience, using fallback")
                                role_data = fallback_role
                            all_experience_results.append(role_data)
                            logger.info(f"[EXPERIENCE CHUNKED] Role {role_position} generated {len(role_data.get('points', []))} bullets")
                        else:
                            logger.warning(f"[EXPERIENCE CHUNKED] Role {role_position} returned unexpected format, using fallback")
                            all_experience_results.append(fallback_role)
                    except asyncio.TimeoutError:
                        logger.error(f"[EXPERIENCE CHUNKED] Role {role_position} TIMEOUT - using original bullets")
                        all_experience_results.append({
                            "company": exp.get("company", ""),
                            "role": exp.get("role", ""),
                            "period": exp.get("period", ""),
                            "points": exp.get("points", exp.get("bullets", []))
                        })
                    except Exception as role_error:
                        logger.error(f"[EXPERIENCE CHUNKED] Role {role_position} ERROR: {str(role_error)}")
                        all_experience_results.append({
                            "company": exp.get("company", ""),
                            "role": exp.get("role", ""),
                            "period": exp.get("period", ""),
                            "points": exp.get("points", exp.get("bullets", []))
                        })
                
                logger.info(f"[EXPERIENCE CHUNKED] Successfully generated {len(all_experience_results)} roles")
                experience_result = clean_experience_bullets(all_experience_results)
                return experience_result
            
            # ============================================================
            # STANDARD PROCESSING: Single LLM call for 1-2 experiences
            # ============================================================
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
                # ============================================================
                # CHUNKED PROCESSING FOR RESUME_JD MODE: 3+ experiences
                # ============================================================
                if num_experiences > CHUNKING_THRESHOLD:
                    logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] Using chunked enhancement for {num_experiences} roles")
                    
                    # Get all keywords
                    all_technical_keywords = jd_hints.get("technical_keywords", [])
                    all_soft_skills = jd_hints.get("soft_skills_role_keywords", [])
                    all_phrases = jd_hints.get("phrases", [])
                    
                    total_keywords = len(all_technical_keywords)
                    total_soft_skills = len(all_soft_skills)
                    total_phrases = len(all_phrases)
                    
                    logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] Total keywords: {total_keywords} technical, {total_soft_skills} soft, {total_phrases} phrases")
                    
                    # Calculate allocation percentages
                    keyword_allocations_rjd = []
                    if num_experiences == 3:
                        keyword_allocations_rjd = [40, 35, 25]
                    elif num_experiences == 4:
                        keyword_allocations_rjd = [35, 30, 20, 15]
                    elif num_experiences >= 5:
                        keyword_allocations_rjd = [35, 25]
                        remaining_pct = 40
                        for _ in range(num_experiences - 2):
                            keyword_allocations_rjd.append(remaining_pct // (num_experiences - 2))
                    
                    # LLM-based keyword categorization
                    existing_skills_rjd = resume_json.get("technical_skills", {})
                    if isinstance(existing_skills_rjd, dict):
                        existing_skills_list_rjd = []
                        for category, skills in existing_skills_rjd.items():
                            if isinstance(skills, list):
                                existing_skills_list_rjd.extend(skills)
                            elif isinstance(skills, str):
                                existing_skills_list_rjd.append(skills)
                        existing_skills_rjd = existing_skills_list_rjd
                    elif not isinstance(existing_skills_rjd, list):
                        existing_skills_rjd = []
                    
                    job_domain_rjd = preprocessed_jd.get("metadata", {}).get("job_title", "Software Engineer")
                    
                    _jd_preferred_rjd = preprocessed_sections.get("preferred", preprocessed_sections.get("nice_to_have", []))
                    _jd_req_text_rjd = " ".join(jd_requirements[:10]) if isinstance(jd_requirements, list) else str(jd_requirements)[:600]
                    _jd_pref_text_rjd = " ".join(_jd_preferred_rjd[:5]) if isinstance(_jd_preferred_rjd, list) else str(_jd_preferred_rjd)[:400]

                    try:
                        logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] Calling LLM to categorize {total_keywords} keywords...")

                        categorization_prompt_rjd = CATEGORIZE_KEYWORDS_PROMPT.format(
                            job_domain=job_domain_rjd,
                            num_roles=num_experiences,
                            jd_requirements_text=_jd_req_text_rjd[:600],
                            jd_preferred_text=_jd_pref_text_rjd[:400],
                            technical_keywords=json.dumps(all_technical_keywords, ensure_ascii=False),
                            existing_skills=json.dumps(existing_skills_rjd[:20], ensure_ascii=False)
                        )

                        categorization_result_raw_rjd = await chat_completion_async(
                            categorization_prompt_rjd,
                            response_schema=categorize_keywords_response_schema,
                            timeout=45
                        )
                        categorization_result_repaired_rjd = repair_json(categorization_result_raw_rjd)
                        categorization_rjd = json.loads(categorization_result_repaired_rjd)

                        competing_groups_rjd = categorization_rjd.get("competing_groups", [])
                        if competing_groups_rjd:
                            for grp in competing_groups_rjd:
                                logger.info(f"[COMPETING TECH RESUME_JD] {grp.get('group_name','?')}: preferred={grp.get('winner','?')}, secondary={grp.get('secondary',[])}, reason={grp.get('reason','')}")

                        core_technical_rjd = categorization_rjd.get("core_keywords", [])
                        supplementary_technical_rjd = categorization_rjd.get("supplementary_keywords", [])
                        supplemented_keywords_rjd = categorization_rjd.get("supplemented_keywords", [])
                        remaining_technical_rjd = supplementary_technical_rjd + supplemented_keywords_rjd

                        logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] LLM categorization: {len(core_technical_rjd)} core, {len(supplementary_technical_rjd)} supplementary")

                    except Exception as cat_error_rjd:
                        logger.warning(f"[EXPERIENCE CHUNKED RESUME_JD] LLM categorization failed: {str(cat_error_rjd)}. Using positional fallback.")
                        core_tech_count_rjd = max(3, total_keywords // 5)
                        core_technical_rjd = all_technical_keywords[:core_tech_count_rjd]
                        remaining_technical_rjd = all_technical_keywords[core_tech_count_rjd:]
                    
                    # Soft skills and phrases use positional splitting
                    core_soft_count_rjd = max(2, total_soft_skills // 5)
                    core_phrase_count_rjd = max(2, total_phrases // 5)
                    core_soft_skills_rjd = all_soft_skills[:core_soft_count_rjd]
                    core_phrases_rjd = all_phrases[:core_phrase_count_rjd]
                    remaining_soft_skills_rjd = all_soft_skills[core_soft_count_rjd:]
                    remaining_phrases_rjd = all_phrases[core_phrase_count_rjd:]
                    
                    # Split remaining keywords by role
                    def split_by_percentages_rjd(items, percentages):
                        chunks = []
                        total = len(items)
                        current_idx = 0
                        for i, pct in enumerate(percentages):
                            if i == len(percentages) - 1:
                                chunk_size = total - current_idx
                            else:
                                chunk_size = max(1, int(total * pct / 100))
                            end_idx = min(current_idx + chunk_size, total)
                            chunks.append(items[current_idx:end_idx])
                            current_idx = end_idx
                        return chunks
                    
                    tech_chunks_rjd = split_by_percentages_rjd(remaining_technical_rjd, keyword_allocations_rjd)
                    soft_chunks_rjd = split_by_percentages_rjd(remaining_soft_skills_rjd, keyword_allocations_rjd)
                    phrase_chunks_rjd = split_by_percentages_rjd(remaining_phrases_rjd, keyword_allocations_rjd)
                    
                    # Enhance each role sequentially
                    all_experience_results_rjd = []
                    for idx, exp in enumerate(experience_data):
                        role_position = idx + 1
                        
                        # Combine core + role-specific keywords
                        role_technical_rjd = core_technical_rjd + (tech_chunks_rjd[idx] if idx < len(tech_chunks_rjd) else [])
                        role_soft_skills_rjd = core_soft_skills_rjd + (soft_chunks_rjd[idx] if idx < len(soft_chunks_rjd) else [])
                        role_phrases_rjd = core_phrases_rjd + (phrase_chunks_rjd[idx] if idx < len(phrase_chunks_rjd) else [])
                        
                        # Get original bullets
                        original_bullets_rjd = exp.get("points", exp.get("bullets", []))
                        
                        logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] Enhancing role {role_position}/{num_experiences}: {exp.get('company', 'Unknown')}")
                        logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] Role {role_position} keywords: {len(role_technical_rjd)} tech, {len(original_bullets_rjd)} bullets to enhance")
                        
                        prompt_rjd = ENHANCE_SINGLE_ROLE_EXPERIENCE_PROMPT.format(
                            role_position=role_position,
                            total_roles=num_experiences,
                            keyword_count=len(role_technical_rjd),
                            role_seniority=role_seniority,
                            role_title=role_title,
                            technical_keywords=json.dumps(role_technical_rjd, ensure_ascii=False),
                            soft_skills=json.dumps(role_soft_skills_rjd, ensure_ascii=False),
                            phrases=json.dumps(role_phrases_rjd, ensure_ascii=False),
                            jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                            company=exp.get("company", ""),
                            role_name=exp.get("role", ""),
                            period=exp.get("period", ""),
                            original_bullets=json.dumps(original_bullets_rjd, ensure_ascii=False, indent=2)
                        )
                        
                        try:
                            result_raw_rjd = await chat_completion_async(prompt_rjd, response_schema=single_role_response_schema, timeout=60)
                            result_raw_repaired_rjd = repair_json(result_raw_rjd)
                            result_rjd = json.loads(result_raw_repaired_rjd)
                            
                            fallback_rjd = {
                                "company": exp.get("company", ""),
                                "role": exp.get("role", ""),
                                "period": exp.get("period", ""),
                                "points": original_bullets_rjd
                            }
                            if isinstance(result_rjd, dict):
                                if "experience" in result_rjd and result_rjd["experience"]:
                                    role_data_rjd = result_rjd["experience"][0]
                                elif "company" in result_rjd or "role" in result_rjd or "points" in result_rjd:
                                    role_data_rjd = result_rjd
                                else:
                                    logger.warning(f"[EXPERIENCE CHUNKED RESUME_JD] Role {role_position} returned empty experience, using original")
                                    role_data_rjd = fallback_rjd
                                all_experience_results_rjd.append(role_data_rjd)
                                logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] Role {role_position} enhanced {len(role_data_rjd.get('points', []))} bullets")
                            else:
                                logger.warning(f"[EXPERIENCE CHUNKED RESUME_JD] Role {role_position} unexpected format, using original")
                                all_experience_results_rjd.append(fallback_rjd)
                        except asyncio.TimeoutError:
                            logger.error(f"[EXPERIENCE CHUNKED RESUME_JD] Role {role_position} TIMEOUT - using original bullets")
                            all_experience_results_rjd.append({
                                "company": exp.get("company", ""),
                                "role": exp.get("role", ""),
                                "period": exp.get("period", ""),
                                "points": original_bullets_rjd
                            })
                        except Exception as role_error_rjd:
                            logger.error(f"[EXPERIENCE CHUNKED RESUME_JD] Role {role_position} ERROR: {str(role_error_rjd)}")
                            all_experience_results_rjd.append({
                                "company": exp.get("company", ""),
                                "role": exp.get("role", ""),
                                "period": exp.get("period", ""),
                                "points": original_bullets_rjd
                            })
                    
                    logger.info(f"[EXPERIENCE CHUNKED RESUME_JD] Successfully enhanced {len(all_experience_results_rjd)} roles")
                    experience_result = clean_experience_bullets(all_experience_results_rjd)
                    return experience_result
                
                # Standard processing for 1-2 experiences
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
            
            # Log raw response for debugging
            logger.info(f"[EXPERIENCE] Raw LLM response length: {len(result_raw)} chars")
            if len(result_raw) < 500:
                logger.warning(f"[EXPERIENCE] ⚠️ Response seems short. Raw content: {result_raw[:500]}")
            
            # Try to repair malformed JSON from LLM response
            result_raw_repaired = repair_json(result_raw)
            if result_raw_repaired != result_raw:
                logger.info(f"[EXPERIENCE] JSON was repaired. Original length: {len(result_raw)}, Repaired length: {len(result_raw_repaired)}")
            
            result = json.loads(result_raw_repaired)
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
            logger.error("[EXPERIENCE] ❌ TIMEOUT after 90 seconds")
            if mode == "complete_jd":
                # Raise exception to fail the job properly
                raise RuntimeError("Experience generation timed out. Please try again.")
            else:
                logger.warning("[EXPERIENCE] resume_jd mode - returning original bullets as fallback")
                return resume_json.get("experience", [])
        except Exception as e:
            logger.error(f"[EXPERIENCE] ❌ ERROR: {str(e)}")
            # Log raw response for debugging JSON parse errors
            if 'result_raw' in locals():
                logger.error(f"[EXPERIENCE] Raw response (first 500 chars): {result_raw[:500] if len(result_raw) > 500 else result_raw}")
                logger.error(f"[EXPERIENCE] Raw response (last 200 chars): {result_raw[-200:] if len(result_raw) > 200 else result_raw}")
            if mode == "complete_jd":
                # Raise exception to fail the job properly
                raise RuntimeError(f"Experience generation failed: {str(e)}. The AI response was incomplete or malformed.")
            else:
                logger.warning("[EXPERIENCE] resume_jd mode - returning original bullets as fallback")
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
    
    try:
        summary, experience, skills = await asyncio.gather(
            generate_summary(),
            generate_experience(),
            generate_skills()
        )
    except RuntimeError as e:
        # Handle generation failures (e.g., experience generation failed in complete_jd mode)
        error_msg = str(e)
        logger.error(f"[GENERATE_RESUME_CONTENT] ❌ Generation failed: {error_msg}")
        send_progress(request_id, 0, f"Error: {error_msg}", db, status="failed")
        
        # Update job in database with error
        if db:
            try:
                job = db.query(ResumeJob).filter(ResumeJob.request_id == request_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = error_msg
                    db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update job status to failed: {db_error}")
        
        raise  # Re-raise to propagate to endpoint
    
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
            result_raw = await chat_completion_async(
                prompt, response_schema=summary_response_schema, timeout=90
            )
            result = json.loads(result_raw)
            logger.info("[SUMMARY] Generated successfully")
            return result.get("summary", "")

        except asyncio.TimeoutError:
            logger.error("[SUMMARY] Timeout after 90 seconds")
            return resume_json.get("summary", "")
        except Exception as e:
            logger.error(f"[SUMMARY] Error: {str(e)}")
            return resume_json.get("summary", "")
    
    async def generate_experience():
        """Generate optimized experience bullets from JD hints.
        Uses chunked processing for 3+ experiences to prevent LLM truncation."""
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
            
            # ============================================================
            # CHUNKED PROCESSING: Use single-role prompts for 3+ experiences
            # to prevent LLM output truncation issues
            # ============================================================
            num_experiences = len(experience_data)
            CHUNKING_THRESHOLD = 2  # Use chunking for more than 2 experiences
            
            if mode == "complete_jd" and num_experiences > CHUNKING_THRESHOLD:
                logger.info(f"[EXPERIENCE CHUNKED] Using chunked generation for {num_experiences} roles (threshold: {CHUNKING_THRESHOLD})")
                
                # Get all keywords
                all_technical_keywords = jd_hints.get("technical_keywords", [])
                all_soft_skills = jd_hints.get("soft_skills_role_keywords", [])
                all_phrases = jd_hints.get("phrases", [])
                
                total_keywords = len(all_technical_keywords)
                total_soft_skills = len(all_soft_skills)
                total_phrases = len(all_phrases)
                
                logger.info(f"[EXPERIENCE CHUNKED] Total keywords to distribute: {total_keywords} technical, {total_soft_skills} soft skills, {total_phrases} phrases")
                
                # Calculate keyword allocation percentages per role
                keyword_allocations = []
                if num_experiences == 3:
                    keyword_allocations = [45, 35, 20]
                elif num_experiences == 4:
                    keyword_allocations = [40, 30, 20, 10]
                elif num_experiences >= 5:
                    keyword_allocations = [40, 25]
                    remaining = 35
                    for _ in range(num_experiences - 2):
                        keyword_allocations.append(remaining // (num_experiences - 2))
                
                # ============================================================
                # LLM-BASED KEYWORD CATEGORIZATION
                # Ask LLM to intelligently identify core vs supplementary keywords
                # Also handles supplementation when keywords are insufficient
                # ============================================================
                
                # Get user's existing skills from resume for supplementation context
                existing_skills = resume_json.get("technical_skills", {})
                if isinstance(existing_skills, dict):
                    existing_skills_list = []
                    for category, skills in existing_skills.items():
                        if isinstance(skills, list):
                            existing_skills_list.extend(skills)
                        elif isinstance(skills, str):
                            existing_skills_list.append(skills)
                    existing_skills = existing_skills_list
                elif not isinstance(existing_skills, list):
                    existing_skills = []
                
                # Get job title/domain for supplementation context
                job_domain = preprocessed_jd.get("metadata", {}).get("job_title", "Software Engineer")
                
                # Call LLM to categorize keywords intelligently (with competing tech resolution)
                _jd_sections_p = preprocessed_jd.get("sections", {})
                _jd_preferred_p = _jd_sections_p.get("preferred", _jd_sections_p.get("nice_to_have", []))
                _jd_req_list_p = _jd_sections_p.get("requirements", [])
                _jd_req_text_p = " ".join(_jd_req_list_p[:10]) if isinstance(_jd_req_list_p, list) else str(_jd_req_list_p)[:600]
                _jd_pref_text_p = " ".join(_jd_preferred_p[:5]) if isinstance(_jd_preferred_p, list) else str(_jd_preferred_p)[:400]

                try:
                    logger.info(f"[EXPERIENCE CHUNKED] Calling LLM to categorize {total_keywords} keywords...")

                    categorization_prompt = CATEGORIZE_KEYWORDS_PROMPT.format(
                        job_domain=job_domain,
                        num_roles=num_experiences,
                        jd_requirements_text=_jd_req_text_p[:600],
                        jd_preferred_text=_jd_pref_text_p[:400],
                        technical_keywords=json.dumps(all_technical_keywords, ensure_ascii=False),
                        existing_skills=json.dumps(existing_skills[:20], ensure_ascii=False)
                    )

                    categorization_result_raw = await chat_completion_async(
                        categorization_prompt,
                        response_schema=categorize_keywords_response_schema,
                        timeout=45
                    )
                    categorization_result_repaired = repair_json(categorization_result_raw)
                    categorization = json.loads(categorization_result_repaired)

                    competing_groups = categorization.get("competing_groups", [])
                    if competing_groups:
                        for grp in competing_groups:
                            logger.info(f"[COMPETING TECH] {grp.get('group_name','?')}: preferred={grp.get('winner','?')}, secondary={grp.get('secondary',[])}, reason={grp.get('reason','')}")

                    core_technical = categorization.get("core_keywords", [])
                    supplementary_technical = categorization.get("supplementary_keywords", [])
                    supplemented_keywords = categorization.get("supplemented_keywords", [])
                    remaining_technical = supplementary_technical + supplemented_keywords

                    logger.info(f"[EXPERIENCE CHUNKED] LLM categorization: {len(core_technical)} core, {len(supplementary_technical)} supplementary, {len(supplemented_keywords)} supplemented")

                except Exception as cat_error:
                    logger.warning(f"[EXPERIENCE CHUNKED] LLM categorization failed: {str(cat_error)}. Using positional fallback.")
                    core_tech_count = max(3, total_keywords // 5)
                    core_technical = all_technical_keywords[:core_tech_count]
                    remaining_technical = all_technical_keywords[core_tech_count:]

                # Soft skills and phrases use positional splitting
                core_soft_count = max(2, total_soft_skills // 5)
                core_phrase_count = max(2, total_phrases // 5)
                core_soft_skills = all_soft_skills[:core_soft_count]
                core_phrases = all_phrases[:core_phrase_count]
                remaining_soft_skills = all_soft_skills[core_soft_count:]
                remaining_phrases = all_phrases[core_phrase_count:]

                logger.info(f"[EXPERIENCE CHUNKED] Final split - Core: {len(core_technical)} tech, {len(core_soft_skills)} soft, {len(core_phrases)} phrases")

                def split_by_percentages(items, percentages):
                    chunks = []
                    total = len(items)
                    current_idx = 0
                    for i, pct in enumerate(percentages):
                        if i == len(percentages) - 1:
                            chunk_size = total - current_idx
                        else:
                            chunk_size = max(1, int(total * pct / 100))
                        end_idx = min(current_idx + chunk_size, total)
                        chunks.append(items[current_idx:end_idx])
                        current_idx = end_idx
                    return chunks
                
                tech_chunks = split_by_percentages(remaining_technical, keyword_allocations)
                soft_chunks = split_by_percentages(remaining_soft_skills, keyword_allocations)
                phrase_chunks = split_by_percentages(remaining_phrases, keyword_allocations)
                
                # Bullet counts: more bullets for recent roles
                bullet_counts = []
                for i in range(num_experiences):
                    if i == 0:
                        bullet_counts.append(8)
                    elif i == 1:
                        bullet_counts.append(7)
                    else:
                        bullet_counts.append(6)
                
                # Generate experience for each role sequentially
                all_experience_results = []
                for idx, exp in enumerate(experience_data):
                    role_position = idx + 1
                    bullet_count = bullet_counts[idx] if idx < len(bullet_counts) else 6
                    
                    # Combine core keywords + role-specific keywords
                    role_technical = core_technical + (tech_chunks[idx] if idx < len(tech_chunks) else [])
                    role_soft_skills = core_soft_skills + (soft_chunks[idx] if idx < len(soft_chunks) else [])
                    role_phrases = core_phrases + (phrase_chunks[idx] if idx < len(phrase_chunks) else [])
                    
                    logger.info(f"[EXPERIENCE CHUNKED] Generating role {role_position}/{num_experiences}: {exp.get('company', 'Unknown')}")
                    logger.info(f"[EXPERIENCE CHUNKED] Role {role_position} keywords: {len(role_technical)} tech, {len(role_soft_skills)} soft, {len(role_phrases)} phrases")
                    
                    prompt = GENERATE_SINGLE_ROLE_EXPERIENCE_PROMPT.format(
                        role_position=role_position,
                        total_roles=num_experiences,
                        keyword_allocation=len(role_technical),
                        bullet_count=bullet_count,
                        role_seniority=role_seniority,
                        role_title=role_title,
                        technical_keywords=json.dumps(role_technical, ensure_ascii=False),
                        soft_skills=json.dumps(role_soft_skills, ensure_ascii=False),
                        phrases=json.dumps(role_phrases, ensure_ascii=False),
                        jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                        company=exp.get("company", ""),
                        role_name=exp.get("role", ""),
                        period=exp.get("period", "")
                    )
                    
                    try:
                        result_raw = await chat_completion_async(prompt, response_schema=single_role_response_schema, timeout=60)
                        result_raw_repaired = repair_json(result_raw)
                        result = json.loads(result_raw_repaired)
                        
                        fallback_role_p = {
                            "company": exp.get("company", ""),
                            "role": exp.get("role", ""),
                            "period": exp.get("period", ""),
                            "points": exp.get("points", exp.get("bullets", []))
                        }
                        if isinstance(result, dict):
                            if "experience" in result and result["experience"]:
                                role_data = result["experience"][0]
                            elif "company" in result or "role" in result or "points" in result:
                                role_data = result
                            else:
                                logger.warning(f"[EXPERIENCE CHUNKED] Role {role_position} returned empty experience, using fallback")
                                role_data = fallback_role_p
                            all_experience_results.append(role_data)
                            logger.info(f"[EXPERIENCE CHUNKED] Role {role_position} generated {len(role_data.get('points', []))} bullets")
                        else:
                            all_experience_results.append(fallback_role_p)
                    except asyncio.TimeoutError:
                        logger.error(f"[EXPERIENCE CHUNKED] Role {role_position} TIMEOUT")
                        all_experience_results.append({
                            "company": exp.get("company", ""),
                            "role": exp.get("role", ""),
                            "period": exp.get("period", ""),
                            "points": exp.get("points", exp.get("bullets", []))
                        })
                    except Exception as role_error:
                        logger.error(f"[EXPERIENCE CHUNKED] Role {role_position} ERROR: {str(role_error)}")
                        all_experience_results.append({
                            "company": exp.get("company", ""),
                            "role": exp.get("role", ""),
                            "period": exp.get("period", ""),
                            "points": exp.get("points", exp.get("bullets", []))
                        })

                logger.info(f"[EXPERIENCE CHUNKED] Successfully generated {len(all_experience_results)} roles")
                experience_result = clean_experience_bullets(all_experience_results)
                return experience_result

            # ============================================================
            # STANDARD PROCESSING: Single LLM call for 1-2 experiences
            # ============================================================
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
                # ============================================================
                # CHUNKED PROCESSING FOR RESUME_JD MODE: 3+ experiences
                # ============================================================
                if num_experiences > CHUNKING_THRESHOLD:
                    logger.info(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Using chunked enhancement for {num_experiences} roles")
                    
                    # Get all keywords
                    all_technical_keywords_p = jd_hints.get("technical_keywords", [])
                    all_soft_skills_p = jd_hints.get("soft_skills_role_keywords", [])
                    all_phrases_p = jd_hints.get("phrases", [])
                    
                    total_keywords_p = len(all_technical_keywords_p)
                    total_soft_skills_p = len(all_soft_skills_p)
                    total_phrases_p = len(all_phrases_p)
                    
                    logger.info(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Total keywords: {total_keywords_p} technical, {total_soft_skills_p} soft, {total_phrases_p} phrases")
                    
                    # Calculate allocation percentages
                    keyword_allocations_p = []
                    if num_experiences == 3:
                        keyword_allocations_p = [40, 35, 25]
                    elif num_experiences == 4:
                        keyword_allocations_p = [35, 30, 20, 15]
                    elif num_experiences >= 5:
                        keyword_allocations_p = [35, 25]
                        remaining_pct_p = 40
                        for _ in range(num_experiences - 2):
                            keyword_allocations_p.append(remaining_pct_p // (num_experiences - 2))
                    
                    # LLM-based keyword categorization
                    existing_skills_p = resume_json.get("technical_skills", {})
                    if isinstance(existing_skills_p, dict):
                        existing_skills_list_p = []
                        for category, skills in existing_skills_p.items():
                            if isinstance(skills, list):
                                existing_skills_list_p.extend(skills)
                            elif isinstance(skills, str):
                                existing_skills_list_p.append(skills)
                        existing_skills_p = existing_skills_list_p
                    elif not isinstance(existing_skills_p, list):
                        existing_skills_p = []
                    
                    job_domain_p = preprocessed_jd.get("metadata", {}).get("job_title", "Software Engineer")
                    
                    _jd_sections_pp = preprocessed_jd.get("sections", {})
                    _jd_preferred_pp = _jd_sections_pp.get("preferred", _jd_sections_pp.get("nice_to_have", []))
                    _jd_req_list_pp = _jd_sections_pp.get("requirements", [])
                    _jd_req_text_pp = " ".join(_jd_req_list_pp[:10]) if isinstance(_jd_req_list_pp, list) else str(_jd_req_list_pp)[:600]
                    _jd_pref_text_pp = " ".join(_jd_preferred_pp[:5]) if isinstance(_jd_preferred_pp, list) else str(_jd_preferred_pp)[:400]

                    try:
                        logger.info(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Calling LLM to categorize {total_keywords_p} keywords...")

                        categorization_prompt_p = CATEGORIZE_KEYWORDS_PROMPT.format(
                            job_domain=job_domain_p,
                            num_roles=num_experiences,
                            jd_requirements_text=_jd_req_text_pp[:600],
                            jd_preferred_text=_jd_pref_text_pp[:400],
                            technical_keywords=json.dumps(all_technical_keywords_p, ensure_ascii=False),
                            existing_skills=json.dumps(existing_skills_p[:20], ensure_ascii=False)
                        )

                        categorization_result_raw_p = await chat_completion_async(
                            categorization_prompt_p,
                            response_schema=categorize_keywords_response_schema,
                            timeout=45
                        )
                        categorization_result_repaired_p = repair_json(categorization_result_raw_p)
                        categorization_p = json.loads(categorization_result_repaired_p)

                        competing_groups_p = categorization_p.get("competing_groups", [])
                        if competing_groups_p:
                            for grp in competing_groups_p:
                                logger.info(f"[COMPETING TECH RESUME_JD_P] {grp.get('group_name','?')}: preferred={grp.get('winner','?')}, secondary={grp.get('secondary',[])}, reason={grp.get('reason','')}")

                        core_technical_p = categorization_p.get("core_keywords", [])
                        supplementary_technical_p = categorization_p.get("supplementary_keywords", [])
                        supplemented_keywords_p = categorization_p.get("supplemented_keywords", [])
                        remaining_technical_p = supplementary_technical_p + supplemented_keywords_p

                        logger.info(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] LLM categorization: {len(core_technical_p)} core, {len(supplementary_technical_p)} supplementary")

                    except Exception as cat_error_p:
                        logger.warning(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] LLM categorization failed: {str(cat_error_p)}. Using positional fallback.")
                        core_tech_count_p = max(3, total_keywords_p // 5)
                        core_technical_p = all_technical_keywords_p[:core_tech_count_p]
                        remaining_technical_p = all_technical_keywords_p[core_tech_count_p:]
                    
                    # Soft skills and phrases use positional splitting
                    core_soft_count_p = max(2, total_soft_skills_p // 5)
                    core_phrase_count_p = max(2, total_phrases_p // 5)
                    core_soft_skills_p = all_soft_skills_p[:core_soft_count_p]
                    core_phrases_p = all_phrases_p[:core_phrase_count_p]
                    remaining_soft_skills_p = all_soft_skills_p[core_soft_count_p:]
                    remaining_phrases_p = all_phrases_p[core_phrase_count_p:]
                    
                    # Split remaining keywords by role
                    def split_by_percentages_p(items, percentages):
                        chunks = []
                        total = len(items)
                        current_idx = 0
                        for i, pct in enumerate(percentages):
                            if i == len(percentages) - 1:
                                chunk_size = total - current_idx
                            else:
                                chunk_size = max(1, int(total * pct / 100))
                            end_idx = min(current_idx + chunk_size, total)
                            chunks.append(items[current_idx:end_idx])
                            current_idx = end_idx
                        return chunks
                    
                    tech_chunks_p = split_by_percentages_p(remaining_technical_p, keyword_allocations_p)
                    soft_chunks_p = split_by_percentages_p(remaining_soft_skills_p, keyword_allocations_p)
                    phrase_chunks_p = split_by_percentages_p(remaining_phrases_p, keyword_allocations_p)
                    
                    # Enhance each role sequentially
                    all_experience_results_p = []
                    for idx, exp in enumerate(experience_data):
                        role_position = idx + 1
                        
                        # Combine core + role-specific keywords
                        role_technical_p = core_technical_p + (tech_chunks_p[idx] if idx < len(tech_chunks_p) else [])
                        role_soft_skills_p = core_soft_skills_p + (soft_chunks_p[idx] if idx < len(soft_chunks_p) else [])
                        role_phrases_p = core_phrases_p + (phrase_chunks_p[idx] if idx < len(phrase_chunks_p) else [])
                        
                        # Get original bullets
                        original_bullets_p = exp.get("points", exp.get("bullets", []))
                        
                        logger.info(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Enhancing role {role_position}/{num_experiences}: {exp.get('company', 'Unknown')}")
                        
                        prompt_p = ENHANCE_SINGLE_ROLE_EXPERIENCE_PROMPT.format(
                            role_position=role_position,
                            total_roles=num_experiences,
                            keyword_count=len(role_technical_p),
                            role_seniority=role_seniority,
                            role_title=role_title,
                            technical_keywords=json.dumps(role_technical_p, ensure_ascii=False),
                            soft_skills=json.dumps(role_soft_skills_p, ensure_ascii=False),
                            phrases=json.dumps(role_phrases_p, ensure_ascii=False),
                            jd_requirements=json.dumps(jd_requirements, ensure_ascii=False),
                            company=exp.get("company", ""),
                            role_name=exp.get("role", ""),
                            period=exp.get("period", ""),
                            original_bullets=json.dumps(original_bullets_p, ensure_ascii=False, indent=2)
                        )
                        
                        try:
                            result_raw_p = await chat_completion_async(prompt_p, response_schema=single_role_response_schema, timeout=60)
                            result_raw_repaired_p = repair_json(result_raw_p)
                            result_p = json.loads(result_raw_repaired_p)
                            
                            fallback_pp = {
                                "company": exp.get("company", ""),
                                "role": exp.get("role", ""),
                                "period": exp.get("period", ""),
                                "points": original_bullets_p
                            }
                            if isinstance(result_p, dict):
                                if "experience" in result_p and result_p["experience"]:
                                    role_data_p = result_p["experience"][0]
                                elif "company" in result_p or "role" in result_p or "points" in result_p:
                                    role_data_p = result_p
                                else:
                                    logger.warning(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Role {role_position} returned empty experience, using original")
                                    role_data_p = fallback_pp
                                all_experience_results_p.append(role_data_p)
                                logger.info(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Role {role_position} enhanced {len(role_data_p.get('points', []))} bullets")
                            else:
                                all_experience_results_p.append(fallback_pp)
                        except asyncio.TimeoutError:
                            logger.error(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Role {role_position} TIMEOUT")
                            all_experience_results_p.append({
                                "company": exp.get("company", ""),
                                "role": exp.get("role", ""),
                                "period": exp.get("period", ""),
                                "points": original_bullets_p
                            })
                        except Exception as role_error_p:
                            logger.error(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Role {role_position} ERROR: {str(role_error_p)}")
                            all_experience_results_p.append({
                                "company": exp.get("company", ""),
                                "role": exp.get("role", ""),
                                "period": exp.get("period", ""),
                                "points": original_bullets_p
                            })
                    
                    logger.info(f"[EXPERIENCE PARALLEL CHUNKED RESUME_JD] Successfully enhanced {len(all_experience_results_p)} roles")
                    experience_result = clean_experience_bullets(all_experience_results_p)
                    return experience_result
                
                # Standard processing for 1-2 experiences
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
            
            # Try to repair malformed JSON from LLM response
            result_raw = repair_json(result_raw)
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
            logger.error("[EXPERIENCE PARALLEL] ❌ TIMEOUT after 90 seconds")
            if mode == "complete_jd":
                raise RuntimeError("Experience generation timed out. Please try again.")
            else:
                logger.warning("[EXPERIENCE PARALLEL] resume_jd mode - returning original bullets as fallback")
                return resume_json.get("experience", [])
        except Exception as e:
            logger.error(f"[EXPERIENCE PARALLEL] ❌ ERROR: {str(e)}")
            if mode == "complete_jd":
                raise RuntimeError(f"Experience generation failed: {str(e)}. The AI response was incomplete or malformed.")
            else:
                logger.warning("[EXPERIENCE PARALLEL] resume_jd mode - returning original bullets as fallback")
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
