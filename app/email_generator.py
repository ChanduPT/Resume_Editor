"""
Email Generator Module
Handles generation of various types of professional emails using AI
"""

import logging
from typing import Optional, Dict, Any
from app.utils import chat_completion_async

logger = logging.getLogger(__name__)


# Email response schema for structured output
email_response_schema = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"}
    },
    "required": ["subject", "body"]
}


async def generate_custom_email(
    request: str,
    context: Optional[str] = None,
    resume_summary: Optional[str] = None,
    tone: str = "professional",
    length: str = "medium",
    resume_data: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Generate ANY type of email based on natural language request.
    This is the most flexible mode - supports unlimited scenarios.
    
    Args:
        request: Natural language description of the email needed
        context: Additional context or details
        resume_summary: User's resume summary if relevant
        tone: Writing tone (professional, enthusiastic, formal, conversational, friendly, assertive)
        length: Email length (short, medium, long)
        resume_data: Full resume data for signature generation
    
    Returns:
        Dictionary with 'subject' and 'body' keys
    """
    
    length_guide = {
        "short": "100-150 words",
        "medium": "200-300 words",
        "long": "400-500 words"
    }
    
    word_count = length_guide.get(length, "200-300 words")
    
    # Get current date and time for accurate context
    from datetime import datetime
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%A, %B %d, %Y")
    current_time = current_datetime.strftime("%I:%M %p")
    
    prompt = f"""You are an expert email writer who can craft ANY type of professional email.

CURRENT DATE: {current_date}
CURRENT TIME: {current_time}

USER REQUEST: {request}

ADDITIONAL CONTEXT: {context or "None provided"}

TONE: {tone}
LENGTH: {length} ({word_count})

{"USER'S RESUME SUMMARY: " + resume_summary if resume_summary else ""}

INSTRUCTIONS:
1. Understand the user's intent from their request
2. Write an appropriate email that fulfills their need
3. Match the requested tone ({tone})
4. Keep the length {length} ({word_count})
5. Use proper email structure (greeting, body)
6. Be specific and actionable
7. Maintain professionalism appropriate to the context
8. If resume summary is provided, naturally incorporate relevant details where appropriate
9. If the request involves replying to an email, match the communication style
10. Include appropriate call-to-action if needed
11. IMPORTANT: When suggesting dates/times for meetings or calls, use realistic future dates based on the current date provided above. Never use past dates.
12. DO NOT include closing ("Best regards", "Sincerely", etc.) or signature - these will be added automatically

Generate:
- An appropriate subject line (concise, clear, relevant)
- A complete email body (well-structured, professional, contextually appropriate, ending with the main content WITHOUT closing salutation)

Return JSON with "subject" and "body" fields.
"""
    
    logger.info(f"Generating custom email - Tone: {tone}, Length: {length}, Has resume_data: {resume_data is not None}")
    
    try:
        response_text = await chat_completion_async(
            prompt=prompt,
            response_schema=email_response_schema
        )
        
        # Parse JSON response
        import json
        response = json.loads(response_text)
        
        email_body = response.get("body", "")
        
        # Append signature if resume data available
        if resume_data:
            logger.info(f"Appending signature. Resume data keys: {list(resume_data.keys())}")
            signature = format_email_signature(resume_data)
            email_body += signature
        else:
            logger.warning("No resume_data provided - signature will not be appended")
        
        return {
            "subject": response.get("subject", ""),
            "body": email_body
        }
    except Exception as e:
        logger.error(f"Error generating custom email: {e}")
        raise


async def generate_template_email(
    email_type: str,
    company: Optional[str] = None,
    job_title: Optional[str] = None,
    jd: Optional[str] = None,
    resume_summary: Optional[str] = None,
    tone: str = "professional",
    length: str = "medium",
    recruiter_email: Optional[str] = None,
    context: Optional[str] = None,
    resume_data: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Handle pre-defined templates for common email scenarios.
    
    Args:
        email_type: Type of email template to use
        company: Company name
        job_title: Job title
        jd: Job description
        resume_summary: User's resume summary
        tone: Writing tone
        length: Email length
        recruiter_email: Recruiter's email content (for replies)
        context: Additional context
    
    Returns:
        Dictionary with 'subject' and 'body' keys
    """
    
    from app.email_prompts import get_email_prompt
    
    length_guide = {
        "short": "100-150 words",
        "medium": "200-300 words",
        "long": "400-500 words"
    }
    
    word_count = length_guide.get(length, "200-300 words")
    
    # Get current date and time for accurate context
    from datetime import datetime
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%A, %B %d, %Y")
    current_time = current_datetime.strftime("%I:%M %p")
    
    try:
        # Get the appropriate prompt template
        prompt_template = get_email_prompt(email_type)
        
        # Format the prompt with provided parameters
        prompt = prompt_template.format(
            current_date=current_date,
            current_time=current_time,
            company=company or "",
            job_title=job_title or "",
            jd=jd or "",
            resume_summary=resume_summary or "",
            tone=tone,
            length=length,
            word_count=word_count,
            recruiter_email=recruiter_email or "",
            context=context or ""
        )
        
        logger.info(f"Generating {email_type} email - Tone: {tone}, Length: {length}, Has resume_data: {resume_data is not None}")
        
        response_text = await chat_completion_async(
            prompt=prompt,
            response_schema=email_response_schema
        )
        
        # Parse JSON response
        import json
        response = json.loads(response_text)
        
        email_body = response.get("body", "")
        
        # Append signature if resume data available
        if resume_data:
            logger.info(f"Appending signature to {email_type} email. Resume data keys: {list(resume_data.keys())}")
            signature = format_email_signature(resume_data)
            email_body += signature
        else:
            logger.warning(f"No resume_data provided for {email_type} email - signature will not be appended")
        
        return {
            "subject": response.get("subject", ""),
            "body": email_body
        }
    except Exception as e:
        logger.error(f"Error generating {email_type} email: {e}")
        raise


def get_user_resume_summary(resume_data: Dict[str, Any]) -> str:
    """
    Extract a concise summary from user's resume data.
    
    Args:
        resume_data: Dictionary containing resume information
    
    Returns:
        String summary of key qualifications
    """
    
    summary_parts = []
    
    # Add name
    if resume_data.get("name"):
        summary_parts.append(f"Name: {resume_data['name']}")
    
    # Add summary/objective
    if resume_data.get("summary"):
        summary_parts.append(f"Summary: {resume_data['summary']}")
    
    # Add key skills
    if resume_data.get("technical_skills"):
        skills = resume_data["technical_skills"]
        if isinstance(skills, dict):
            all_skills = []
            for category, skill_list in skills.items():
                if isinstance(skill_list, list):
                    all_skills.extend(skill_list[:3])  # Top 3 from each category
            if all_skills:
                summary_parts.append(f"Key Skills: {', '.join(all_skills[:8])}")
    
    # Add latest experience
    if resume_data.get("experience") and len(resume_data["experience"]) > 0:
        latest_exp = resume_data["experience"][0]
        exp_text = f"Current/Latest: {latest_exp.get('role', '')} at {latest_exp.get('company', '')}"
        summary_parts.append(exp_text)
    
    # Add education
    if resume_data.get("education") and len(resume_data["education"]) > 0:
        latest_edu = resume_data["education"][0]
        edu_text = f"Education: {latest_edu.get('degree', '')} from {latest_edu.get('institution', '')}"
        summary_parts.append(edu_text)
    
    return "\n".join(summary_parts)


def format_email_signature(resume_data: Dict[str, Any]) -> str:
    """
    Format a professional email signature from resume data.
    
    Args:
        resume_data: Dictionary containing resume information
    
    Returns:
        Formatted signature block ready for copy-paste
    """
    
    name = resume_data.get("name", "")
    contact = resume_data.get("contact", {})
    
    logger.info(f"Formatting signature - Name: {name}, Contact keys: {list(contact.keys()) if contact else 'None'}")
    
    # Extract contact information
    email = contact.get("email", "")
    phone = contact.get("phone", "")
    linkedin = contact.get("linkedin", "")
    portfolio = contact.get("portfolio", "")
    github = contact.get("github", "")
    
    # Build signature starting with closing
    signature_lines = ["\n\nBest regards,"]
    
    if name:
        signature_lines.append(name)
    
    # Add mandatory contact info (no labels)
    if email:
        signature_lines.append(email)
    if phone:
        signature_lines.append(phone)
    
    return "\n".join(signature_lines)
