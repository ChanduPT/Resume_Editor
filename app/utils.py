# app/utils.py

from pathlib import Path
import re
import os
from typing import Dict, Optional, List
import json
from .prompts import PARSE_EXPERIENCE_PROMPT, PARSE_SKILLS_PROMPT
from openai import OpenAI

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


try:  # optional dependency for local .env support
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional
    load_dotenv = None


if load_dotenv:
    # Load a project-level .env once (if it exists) without overriding explicit env vars
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():  # pragma: no cover - filesystem dependent
        load_dotenv(env_path, override=False)

def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", text)).strip()

def split_resume_sections(text: str) -> Dict[str, str]:
    # More flexible splitter that allows other text on the header line
    sections = {
        "Summary": "", "Skills": "", "Experience": "",
        "Projects": "", "Education": "", "Certifications": ""
    }
    
    # Regex to find headers that start a line, case-insensitive
    # This will now match "PROJECTS - GITHUB | TABLEAU"
    header_pattern = r"(?im)^(?P<header>summary|professional summary|skills|technical skills|experience|work experience|professional experience|projects|education|certifications?)(?P<rest>.*)"
    
    lines = text.splitlines()
    current_section_key = None
    content_buffer: List[str] = []

    # Default to summary if no headers are found at all
    if not re.search(header_pattern, text):
        sections["Summary"] = text
        return sections

    for line in lines:
        match = re.match(header_pattern, line)
        if match:
            # When a new header is found, save the previous section's content
            if current_section_key:
                sections[current_section_key] = "\n".join(content_buffer).strip()
                content_buffer = []

            header_text = match.group("header").strip().lower()
            
            # Normalize header to one of the canonical keys
            if "summary" in header_text: current_section_key = "Summary"
            elif "skill" in header_text: current_section_key = "Skills"
            elif "experience" in header_text: current_section_key = "Experience"
            elif "project" in header_text: current_section_key = "Projects"
            elif "education" in header_text: current_section_key = "Education"
            elif "cert" in header_text: current_section_key = "Certifications"
            else: current_section_key = None # Should not happen with this regex

            # Add the rest of the line (if any) to the new section's content
            rest_of_line = match.group("rest").strip()
            # Clean up common separators like ":" or "-"
            if rest_of_line.startswith((":", "-", "|", "—")):
                rest_of_line = rest_of_line[1:].strip()
            if rest_of_line:
                content_buffer.append(rest_of_line)
        
        elif current_section_key:
            # If we are inside a section, append the line
            content_buffer.append(line)
        else:
            # Content before the first header (likely contact info) is ignored for now
            pass

    # Save the last section's content
    if current_section_key:
        sections[current_section_key] = "\n".join(content_buffer).strip()

    return {k: v for k, v in sections.items() if v}

# Provider helper
def _provider() -> str:
    """
    Returns the LLM provider to use.
    Supported: OPENAI (default), GEMINI
    Controlled via env var LLM_PROVIDER.
    """
    return os.getenv("LLM_PROVIDER", "OPENAI").upper()

def openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it or add it to a .env file."
        )
    return OpenAI(api_key=api_key)

def chat_completion(prompt: str, model: Optional[str] = None) -> str:
    """
    Provider-agnostic completion:
    - If LLM_PROVIDER=GEMINI, uses Google Gemini via google-generativeai.
      Requires GEMINI_API_KEY and optional GEMINI_MODEL (defaults to gemini-1.5-flash).
    - Otherwise uses OpenAI Chat Completions (requires OPENAI_API_KEY and optional OPENAI_MODEL).
    """
    provider = _provider()

    if provider == "GEMINI":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Export it or add it to a .env file.")
        try:
            import google.generativeai as genai  # lazy import so dependency is optional
        except ImportError as e:
            raise ImportError(
                "google-generativeai not installed. Run: pip install google-generativeai"
            ) from e

        genai.configure(api_key=api_key)
        model_name = "gemini-2.5-flash"
        gmodel = genai.GenerativeModel(model_name)
        response = gmodel.generate_content(prompt)

        # Primary text
        text = getattr(response, "text", None)
        if text:
            return text.strip()

        # Fallback extraction if needed
        candidates = getattr(response, "candidates", None)
        if candidates:
            parts = []
            for cand in candidates:
                content = getattr(cand, "content", None)
                if content and hasattr(content, "parts"):
                    parts.extend([str(p) for p in content.parts])
            return "\n".join(parts).strip()

        return ""

    else:
        # Default to OpenAI
        client = openai_client()
        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()



def parse_skills_to_json(skills_text: str) -> Dict[str, List[str]]:
    """
    Uses an LLM to parse the skills section text into a structured JSON object with categories.
    """
    if not skills_text.strip():
        return {}

    # Define standard skill categories
    standard_categories = {
        "Programming Languages": [],
        "Data & Business Intelligence": [],
        "Databases & Big Data": [],
        "Cloud Technologies": [],
        "Tools & Frameworks": [],
        "Business & Professional Skills": [],
        "Certifications & Training": []
    }

    prompt = PARSE_SKILLS_PROMPT.format(skills_text=skills_text)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response_text = chat_completion(prompt, model=model)
    
    try:
        if response_text.startswith("```json"):
            response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
        parsed = json.loads(response_text)
        
        # Merge parsed skills into standard categories
        result = standard_categories.copy()
        for cat, skills in parsed.items():
            # Map to standard category or create new one if unique
            if cat in result:
                result[cat].extend(skills)
            else:
                # Try to map to closest standard category
                mapped = False
                for std_cat in standard_categories:
                    if any(kw in cat.lower() for kw in std_cat.lower().split()):
                        result[std_cat].extend(skills)
                        mapped = True
                        break
                if not mapped:
                    result[cat] = skills
        
        # Remove empty categories and sort skills within categories
        return {k: sorted(set(v)) for k, v in result.items() if v}
    except (json.JSONDecodeError, AttributeError):
        return standard_categories

def parse_experience_to_json(experience_text: str) -> List[Dict[str, str]]:
    """
    Uses an LLM to parse the experience section text into a structured JSON list.
    """
    logger.debug("=== Starting experience parsing ===")
    logger.debug(f"Input text length: {len(experience_text) if experience_text else 0}")
    
    if not experience_text or not experience_text.strip():
        logger.warning("Empty experience text provided")
        return []

    try:
        # Format prompt and log
        # Use safe substitution to avoid interpreting JSON braces in the prompt
        prompt = PARSE_EXPERIENCE_PROMPT.replace("{experience_text}", experience_text)
        logger.debug("Formatted prompt successfully")
        logger.debug(f"Prompt preview: {prompt[:200]}...")
        
        # Get model response
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        logger.debug(f"Using model: {model}")
        response_text = chat_completion(prompt, model=model)
        logger.debug(f"Got response of length: {len(response_text)}")
        logger.debug(f"Response preview: {response_text[:200]}...")
        
        # Clean up response
        response_text = response_text.strip()
        logger.debug("Initial response cleanup complete")
        
        if response_text.startswith('```json'):
            logger.debug("Found JSON code block markers")
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        logger.debug("=== Cleaned Response ===")
        logger.debug(response_text)
        logger.debug("========================")
        
        # Parse JSON
        try:
            parsed = json.loads(response_text)
            logger.debug(f"Successfully parsed JSON of type: {type(parsed)}")
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing failed: {str(je)}")
            logger.error("Position of error: " + str(je.pos))
            logger.error("Line of error: " + str(je.lineno))
            logger.error("Column of error: " + str(je.colno))
            logger.error("Full response for debugging:")
            logger.error(response_text)
            raise

        # Handle response types
        if isinstance(parsed, dict):
            logger.debug("Converting single dict to list")
            return [parsed]
        elif isinstance(parsed, list):
            logger.debug(f"Got list of {len(parsed)} experiences")
            return parsed
        else:
            logger.error(f"Unexpected JSON structure type: {type(parsed)}")
            logger.error(f"Content: {parsed}")
            return []
            
    except Exception as e:
        logger.exception("Error in parse_experience_to_json:")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Full traceback:", exc_info=True)
        logger.error("Input text preview:")
        logger.error(experience_text[:500] if experience_text else "None")
        return []
    