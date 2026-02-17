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


def repair_json(json_str: str) -> str:
    """
    Attempt to repair malformed JSON from LLM responses.
    Common issues: unterminated strings, missing closing brackets/braces, trailing commas.
    
    Args:
        json_str: The potentially malformed JSON string
        
    Returns:
        Repaired JSON string (or original if already valid)
    """
    if not json_str:
        return json_str
    
    # First try to parse as-is
    try:
        json.loads(json_str)
        return json_str  # Already valid
    except json.JSONDecodeError:
        pass
    
    logger.warning("[JSON_REPAIR] Attempting to repair malformed JSON...")
    repaired = json_str.strip()
    
    # Remove markdown code blocks if present
    if repaired.startswith("```json"):
        repaired = repaired[7:]
    elif repaired.startswith("```"):
        repaired = repaired[3:]
    if repaired.endswith("```"):
        repaired = repaired[:-3]
    repaired = repaired.strip()
    
    # Strategy 1: Find the last complete bullet point ending with "
    # This handles truncation mid-sentence
    last_complete_bullet = -1
    
    # Look for patterns like: "..." followed by comma or bracket
    import re
    # Find all positions where a string ends properly (not mid-word)
    bullet_endings = list(re.finditer(r'"\s*[,\]\}]', repaired))
    if bullet_endings:
        last_match = bullet_endings[-1]
        # Check if this is inside the points array
        last_complete_bullet = last_match.end() - 1
        logger.info(f"[JSON_REPAIR] Found last complete string at position {last_complete_bullet}")
    
    # If we can find a truncation point, use it
    if last_complete_bullet > 0:
        repaired = repaired[:last_complete_bullet + 1]
    
    # Count remaining open brackets/braces and close them
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False
    
    for char in repaired:
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            open_braces += 1
        elif char == '}':
            open_braces -= 1
        elif char == '[':
            open_brackets += 1
        elif char == ']':
            open_brackets -= 1
    
    # Remove trailing comma if present
    repaired = repaired.rstrip()
    if repaired.endswith(','):
        repaired = repaired[:-1]
    
    # Add missing closing brackets/braces
    repaired += ']' * open_brackets
    repaired += '}' * open_braces
    
    # Try to parse the repaired JSON
    try:
        json.loads(repaired)
        logger.info(f"[JSON_REPAIR] Successfully repaired JSON (added {open_brackets} ] and {open_braces} }})")
        return repaired
    except json.JSONDecodeError as e:
        logger.error(f"[JSON_REPAIR] Failed to repair JSON: {e}")
        # Return original - let caller handle the error
        return json_str


def clean_job_description(jd_text: str) -> str:
    """
    Clean and sanitize job description text by removing extra spaces,
    special characters, and normalizing formatting.
    
    Args:
        jd_text: Raw job description text
        
    Returns:
        Cleaned job description text with normalized spacing and characters
    """
    if not jd_text or not jd_text.strip():
        return ""
    
    # Remove null bytes and other control characters (except newlines, tabs)
    jd_text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', jd_text)
    
    # Replace multiple types of quotes with standard quotes
    jd_text = re.sub(r'[''`]', "'", jd_text)
    jd_text = re.sub(r'[""«»]', '"', jd_text)
    
    # Replace various dash types with standard hyphen
    jd_text = re.sub(r'[—–−]', '-', jd_text)
    
    # Replace bullet points and special symbols with standard dash
    jd_text = re.sub(r'[•●○◦■□▪▫⬤⚫⚪◆◇★☆✓✔✗✘]', '-', jd_text)
    
    # Remove zero-width spaces and other invisible characters
    jd_text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060\ufeff]', '', jd_text)
    
    # Normalize multiple spaces to single space
    jd_text = re.sub(r'[ \t]+', ' ', jd_text)
    
    # Normalize multiple newlines to maximum of 2 (preserve paragraph breaks)
    jd_text = re.sub(r'\n{3,}', '\n\n', jd_text)
    
    # Remove spaces at the beginning and end of each line
    lines = [line.strip() for line in jd_text.split('\n')]
    jd_text = '\n'.join(lines)
    
    # Remove empty lines at the start and end
    jd_text = jd_text.strip()
    
    return jd_text


def clean_experience_bullets(experience_data: list) -> list:
    """
    Clean experience bullets by removing markdown formatting, excessive quotes,
    and other unwanted formatting artifacts from LLM output.
    
    Args:
        experience_data: List of experience objects with 'points' arrays
        
    Returns:
        Cleaned experience data with formatting removed from bullets
    """
    if not experience_data:
        return experience_data
    
    cleaned_experience = []
    
    for exp in experience_data:
        if not isinstance(exp, dict):
            cleaned_experience.append(exp)
            continue
            
        cleaned_exp = exp.copy()
        
        # Clean the bullet points
        if 'points' in cleaned_exp and isinstance(cleaned_exp['points'], list):
            cleaned_points = []
            
            for bullet in cleaned_exp['points']:
                if not isinstance(bullet, str):
                    cleaned_points.append(bullet)
                    continue
                
                # Remove markdown bold (**text** or __text__)
                bullet = re.sub(r'\*\*([^*]+)\*\*', r'\1', bullet)
                bullet = re.sub(r'__([^_]+)__', r'\1', bullet)
                
                # Remove markdown italic (*text* or _text_)
                bullet = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'\1', bullet)
                bullet = re.sub(r'(?<!_)_(?!_)([^_]+)_(?!_)', r'\1', bullet)
                
                # Remove excessive quotes (3+ quotes in a row)
                bullet = re.sub(r"'{3,}", "'", bullet)
                bullet = re.sub(r'"{3,}', '"', bullet)
                
                # Fix excessive apostrophes around words (''"word"'' → "word")
                bullet = re.sub(r"'{2,}\"([^\"]+)\"'{2,}", r'"\1"', bullet)
                bullet = re.sub(r"\"{2,}'([^']+)'\"{2,}", r"'\1'", bullet)
                
                # Remove stray markdown characters at start/end
                bullet = re.sub(r'^[\*_]+|[\*_]+$', '', bullet)
                
                # Normalize multiple spaces
                bullet = re.sub(r'\s+', ' ', bullet)
                
                # Clean up spacing around punctuation
                bullet = re.sub(r'\s+([.,;:])', r'\1', bullet)
                bullet = re.sub(r'([.,;:])\s+', r'\1 ', bullet)
                
                # Trim whitespace
                bullet = bullet.strip()
                
                cleaned_points.append(bullet)
            
            cleaned_exp['points'] = cleaned_points
        
        cleaned_experience.append(cleaned_exp)
    
    return cleaned_experience


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
        # Set max_output_tokens to handle large resumes with multiple experiences
        generation_config = {
            "temperature": 0.2,
            "max_output_tokens": 16384,
        }
        gmodel = genai.GenerativeModel(model_name, generation_config=generation_config)
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


async def chat_completion_async(prompt: str, response_schema: Optional[dict] = None, model: Optional[str] = None, timeout: int = 120, max_retries: int = 3) -> str:
    """
    Async version of chat_completion for parallel API calls with retry logic.
    Supports structured JSON output via response_schema parameter.
    
    Args:
        prompt: The prompt to send to the LLM
        response_schema: Optional JSON schema to enforce structured output (Gemini only)
        model: Optional model override
        timeout: Timeout in seconds (default: 120)
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        str: LLM response text (JSON string if response_schema is provided)
    
    Raises:
        asyncio.TimeoutError: If the LLM call exceeds the timeout after all retries
        RuntimeError: If all retries fail
    """
    import asyncio
    provider = _provider()

    if provider == "GEMINI":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Export it or add it to a .env file.")
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError(
                "google-generativeai not installed. Run: pip install google-generativeai"
            ) from e

        genai.configure(api_key=api_key)
        model_name = "gemini-2.5-flash"
        #model_name = "gemini-3-flash-preview"
        
        # Configure generation with response schema if provided
        # Set max_output_tokens high enough to handle large resumes with multiple experiences
        # Each experience can have 5-6 bullets of ~25 words each = ~150 words per role
        # Plus JSON overhead and multiple roles
        # Setting to 16384 tokens to prevent truncation
        generation_config = {
            "temperature": 0.2,
            "max_output_tokens": 16384,
        }
        
        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema
        
        gmodel = genai.GenerativeModel(
            model_name,
            generation_config=generation_config
        )
        
        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, gmodel.generate_content, prompt),
                    timeout=timeout
                )
                
                # Success - return response
                text = getattr(response, "text", None)
                if text:
                    return text.strip()
                    
                # Fallback extraction
                candidates = getattr(response, "candidates", None)
                if candidates:
                    parts = []
                    for cand in candidates:
                        content = getattr(cand, "content", None)
                        if content and hasattr(content, "parts"):
                            parts.extend([str(p) for p in content.parts])
                    result = "\n".join(parts).strip()
                    if result:
                        return result
                        
            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1  # 1s, 2s, 4s
                    logger.warning(f"LLM timeout on attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"LLM error on attempt {attempt + 1}/{max_retries}: {str(e)}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                continue
        
        # All retries failed
        if last_error:
            raise RuntimeError(f"LLM call failed after {max_retries} attempts: {str(last_error)}")
        raise RuntimeError(f"LLM call returned no content after {max_retries} attempts")

        return ""

    else:
        # Default to OpenAI (async not implemented yet, fallback to sync in thread pool)
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, chat_completion, prompt, model),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"LLM call timed out after {timeout} seconds")



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


def parse_resume_text_to_json(resume_text: str) -> dict:
    """
    Convert extracted resume text to structured JSON using LLM.
    
    Args:
        resume_text: Raw text extracted from resume document
        
    Returns:
        Structured resume data as dict matching the application's format
        
    Raises:
        ValueError: If parsing fails or LLM returns invalid JSON
    """
    from .prompts import PARSE_RESUME_TEXT_PROMPT
    
    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is empty")
    
    try:
        prompt = PARSE_RESUME_TEXT_PROMPT.format(resume_text=resume_text)
        logger.info("Calling LLM to parse resume text to JSON")
        
        response = chat_completion(prompt)
        
        # Extract JSON from response
        logger.debug("=== Raw LLM Response ===")
        logger.debug(response[:500] if len(response) > 500 else response)
        logger.debug("========================")
        
        # Clean response - remove markdown code blocks
        response_text = response.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        elif response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON
        try:
            parsed_data = json.loads(response_text)
            logger.info("Successfully parsed resume to JSON")
            
            # Validate required fields
            if not isinstance(parsed_data, dict):
                raise ValueError("Parsed data is not a dictionary")
            
            # Ensure required top-level keys exist
            required_keys = ['name', 'contact', 'technical_skills', 'experience', 'education']
            for key in required_keys:
                if key not in parsed_data:
                    logger.warning(f"Missing required key: {key}")
                    if key in ['contact', 'technical_skills']:
                        parsed_data[key] = {}
                    elif key in ['experience', 'education', 'certifications', 'projects']:
                        parsed_data[key] = []
                    else:
                        parsed_data[key] = ""
            
            return parsed_data
            
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing failed: {str(je)}")
            logger.error(f"Position: {je.pos}, Line: {je.lineno}, Column: {je.colno}")
            logger.error("Response that failed to parse:")
            logger.error(response_text)
            raise ValueError(f"Failed to parse LLM response as JSON: {str(je)}")
            
    except Exception as e:
        logger.exception("Error in parse_resume_text_to_json:")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error message: {str(e)}")
        raise ValueError(f"Failed to parse resume: {str(e)}")
    
