# app/helpers.py
# Helper functions for resume processing

import json
import re
import os
import tempfile
import traceback
import random
from typing import Dict, List, Any
from datetime import datetime
import logging

from app.utils import chat_completion
from app.prompts import BALANCE_BULLETS_PROMPT

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    """Extract JSON from text that might contain markdown code blocks or other content."""
    try:
        # First try direct JSON parsing
        return json.loads(text)
    except json.JSONDecodeError:
        # Remove markdown code blocks (```json ... ``` or ``` ... ```)
        cleaned = re.sub(r'```(?:json)?\s*\n?', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'```\s*$', '', cleaned)
        cleaned = cleaned.strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON between curly braces
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
    return None


def safe_load_json(raw: str):
    """Safely load JSON from string with fallback extraction"""
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


def normalize_section_name(name: str) -> str:
    """Normalize section names to standard format"""
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


def save_debug_file(content: Any, filename: str, prefix: str = "debug") -> None:
    """Save content to a debug file with timestamp."""
    try:
        debug_dir = os.path.join(os.getcwd(), "debug_files")
        
        # Ensure directory exists and is writable
        os.makedirs(debug_dir, exist_ok=True)
        if not os.access(debug_dir, os.W_OK):
            os.chmod(debug_dir, 0o755)
            
        # Generate unique filename with timestamp
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


def balance_experience_roles(experience_json: List[dict], jd_hints: str) -> List[dict]:
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
