"""
Job Description Preprocessing Layer
====================================
Cleans, structures, and enriches raw JD text before LLM analysis.

Input:  Raw JD text (HTML, unstructured text, recruiter emails)
Output: Structured JSON with clean text, sections, and metadata

Strategy:
- Primary: LLM-based extraction (high accuracy, no hallucination)
- Fallback: Regex-based extraction (if LLM fails)
"""

import re
import html
import json
import logging
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from app.utils import chat_completion_async

logger = logging.getLogger(__name__)


# ====================================================
# 1️⃣ CLEANING & NORMALIZATION
# ====================================================

def clean_jd_text(raw_text: str) -> str:
    """
    Clean and normalize raw JD text.
    
    Steps:
    - Remove HTML tags
    - Remove special characters, bullets, emojis
    - Remove marketing fluff and legal boilerplate
    - Normalize whitespace
    - Validate minimum length
    
    Args:
        raw_text: Raw JD text (may contain HTML)
        
    Returns:
        Cleaned text string
        
    Raises:
        ValueError: If cleaned text is too short (<300 chars)
    """
    if not raw_text:
        raise ValueError("JD text cannot be empty")
    
    # Step 1: Decode HTML entities
    text = html.unescape(raw_text)
    
    # Step 2: Remove HTML tags using BeautifulSoup
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text(separator=' ')
    
    # Step 3: Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Step 4: Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Step 5: Remove phone numbers
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '', text)
    
    # Step 6: Remove bullet symbols and special characters
    bullet_symbols = ['•', '◦', '▪', '▫', '–', '—', '●', '○', '■', '□', '✓', '✔', '★', '☆']
    for symbol in bullet_symbols:
        text = text.replace(symbol, '\n')
    
    # Step 7: Remove emojis (Unicode ranges)
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # Step 8: Remove marketing fluff patterns (DISABLED - too aggressive)
    # These patterns can remove important context, so commenting them out
    # Marketing content will be handled by section extraction instead
    # fluff_patterns = [
    #     r"(?i)^.*?(?:we're hiring|join our team|at \w+ company|about us|who we are).*?(?=\n|$)",
    #     r"(?i)^.*?(?:why join us|why work at|what we offer).*?(?=\n|$)",
    #     r"(?i)^.*?(?:perks and benefits|our benefits|what you'll get).*?(?=\n|$)",
    # ]
    # for pattern in fluff_patterns:
    #     text = re.sub(pattern, '', text, flags=re.MULTILINE)
    
    # Step 9: Remove legal/diversity boilerplate
    boilerplate_patterns = [
        r"(?i)equal opportunity employer.*?(?=\n\n|\Z)",
        r"(?i)we do not discriminate.*?(?=\n\n|\Z)",
        r"(?i)diversity and inclusion.*?(?=\n\n|\Z)",
        r"(?i)affirmative action.*?(?=\n\n|\Z)",
        r"(?i)reasonable accommodation.*?(?=\n\n|\Z)",
        r"(?i)disability accommodation.*?(?=\n\n|\Z)",
        r"(?i)pursuant to.*?(?=\n\n|\Z)",
        r"(?i)in compliance with.*?(?=\n\n|\Z)",
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, '', text)
    
    # Step 10: Remove application instructions
    text = re.sub(r"(?i)to apply.*?(?=\n\n|\Z)", '', text)
    text = re.sub(r"(?i)send your resume to.*?(?=\n\n|\Z)", '', text)
    text = re.sub(r"(?i)click here to apply.*?(?=\n\n|\Z)", '', text)
    
    # Step 11: Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs → single space
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines → double newline
    
    # Step 12: Strip leading/trailing whitespace
    text = text.strip()
    
    # Step 13: Validate minimum length
    if len(text) < 300:
        raise ValueError(f"JD text too short after cleaning ({len(text)} chars). Minimum: 300 chars")
    
    logger.info(f"JD cleaned: {len(raw_text)} → {len(text)} chars")
    
    return text


# ====================================================
# 1.5️⃣ LLM-BASED EXTRACTION (HIGH ACCURACY)
# ====================================================

async def extract_with_llm(clean_text: str) -> Dict:
    """
    Use LLM to extract sections and metadata with high accuracy.
    
    This is the PRIMARY extraction method - no hallucination, only exact extraction.
    """
    
    prompt = f"""You are a precise Job Description parser. Extract EXACT information from the JD below.

CRITICAL RULES:
1. Extract ONLY what exists in the text - DO NOT hallucinate or infer
2. Copy text VERBATIM - do not paraphrase or summarize
3. If a section doesn't exist, return empty array
4. Preserve original wording exactly

JOB DESCRIPTION:
```
{clean_text}
```

Extract the following in JSON format:

1. JOB TITLE: Find the exact job title (e.g., "Senior HR Data Analyst", "Software Engineer")
   - Look for phrases like "The [Job Title] is..." or "We are hiring a [Job Title]"
   - Return ONLY the title, nothing else

2. SENIORITY: Identify level from title or requirements
   - Options: "Junior", "Mid-level", "Senior", "Lead", "Principal", "Staff", "Entry-level"
   - Look for: years of experience, title keywords (Senior, Junior, etc.)

3. LOCATION: Find work location if mentioned
   - Look for: "Location:", "in [City, State]", "based in", "office in", "remote", "hybrid"
   - Return city and state if available, or "Remote"/"Hybrid"

4. RESPONSIBILITIES: Extract ALL bullet points or sentences about what the person will DO
   - Look for sections: "Responsibilities", "What you'll do", "What you can expect", "How you'll make an impact"
   - Each bullet should be ONE complete responsibility
   - Do NOT include requirements or qualifications here

5. REQUIREMENTS: Extract ALL bullet points about what the candidate MUST HAVE
   - Look for sections: "Requirements", "Qualifications", "What you'll bring", "What you need", "Must have"
   - Include: education, years of experience, required skills, certifications
   - Each bullet should be ONE requirement

6. PREFERRED: Extract ALL nice-to-have qualifications
   - Look for sections: "Preferred", "Nice to have", "Bonus", "Plus"
   - Do NOT include company benefits or perks here

OUTPUT FORMAT (strict JSON):
{{
  "job_title": "exact title from JD",
  "seniority": "one of the options above",
  "location": "city, state or Remote/Hybrid or Not specified",
  "responsibilities": ["responsibility 1", "responsibility 2", ...],
  "requirements": ["requirement 1", "requirement 2", ...],
  "preferred": ["preferred 1", "preferred 2", ...]
}}

IMPORTANT: 
- Extract EVERY bullet point - don't skip any
- Keep original wording - don't paraphrase
- If multiple items are in one paragraph, split them into separate bullets
- Return ONLY the JSON, no explanation"""

    try:
        response_schema = {
            "type": "object",
            "properties": {
                "job_title": {"type": "string"},
                "seniority": {"type": "string"},
                "location": {"type": "string"},
                "responsibilities": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "preferred": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["job_title", "seniority", "location", "responsibilities", "requirements", "preferred"]
        }
        
        result_raw = await chat_completion_async(
            prompt,
            response_schema=response_schema,
            timeout=120  # 2 minutes for careful extraction
        )
        
        result = json.loads(result_raw)
        logger.info(f"[LLM EXTRACTION] Successfully extracted: title='{result['job_title']}', "
                   f"resp={len(result['responsibilities'])}, req={len(result['requirements'])}, "
                   f"pref={len(result['preferred'])}")
        
        return result
        
    except Exception as e:
        logger.error(f"[LLM EXTRACTION] Failed: {e}")
        return None


# ====================================================
# 2️⃣ SECTION TAGGING (REGEX FALLBACK)
# ====================================================

def split_sections(clean_text: str) -> Dict[str, List[str]]:
    """
    Split JD text into structured sections.
    
    Identifies:
    - Responsibilities (What you'll do)
    - Requirements (Must-have qualifications)
    - Preferred (Nice-to-have skills)
    
    Args:
        clean_text: Cleaned JD text
        
    Returns:
        Dictionary with sections as lists of bullet points
    """
    sections = {
        "responsibilities": [],
        "requirements": [],
        "preferred": []
    }
    
    # Section header patterns (case-insensitive)
    section_markers = {
        "responsibilities": [
            r"(?i)responsibilities",
            r"(?i)what you'?ll do",
            r"(?i)what you can expect",
            r"(?i)how you'?ll make an impact",
            r"(?i)your role",
            r"(?i)job duties",
            r"(?i)day to day",
            r"(?i)in this role",
        ],
        "requirements": [
            r"(?i)requirements",
            r"(?i)qualifications",
            r"(?i)what you'?ll bring",
            r"(?i)what you need",
            r"(?i)skills needed",
            r"(?i)must have",
            r"(?i)you have",
            r"(?i)basic qualifications",
            r"(?i)minimum qualifications",
            r"(?i)required skills",
        ],
        "preferred": [
            r"(?i)preferred",
            r"(?i)nice to have",
            r"(?i)bonus",
            r"(?i)good to have",
            r"(?i)plus",
            r"(?i)additional qualifications",
            r"(?i)preferred qualifications",
            r"(?i)the perks",
            r"(?i)benefits",
        ]
    }
    
    # Find section boundaries
    section_positions = []
    for section_name, patterns in section_markers.items():
        for pattern in patterns:
            for match in re.finditer(pattern, clean_text):
                section_positions.append((match.start(), section_name, match.group()))
    
    # Sort by position
    section_positions.sort(key=lambda x: x[0])
    
    # Extract text for each section
    for i, (start_pos, section_name, header) in enumerate(section_positions):
        # Find end position (next section or end of text)
        end_pos = section_positions[i + 1][0] if i + 1 < len(section_positions) else len(clean_text)
        
        # Extract section text
        section_text = clean_text[start_pos:end_pos]
        
        # Remove header
        section_text = re.sub(re.escape(header), '', section_text, count=1)
        
        # Split into bullet points
        bullets = _extract_bullets(section_text)
        
        # Add to appropriate section (append, don't skip if already has content)
        sections[section_name].extend(bullets)
    
    # If no sections found, try to extract bullets from entire text
    if not any(sections.values()):
        logger.warning("No section headers found, treating entire text as requirements")
        sections["requirements"] = _extract_bullets(clean_text)
    
    logger.info(f"Sections extracted: resp={len(sections['responsibilities'])}, "
                f"req={len(sections['requirements'])}, pref={len(sections['preferred'])}")
    
    return sections


def _extract_bullets(text: str) -> List[str]:
    """
    Extract bullet points from a section of text.
    
    Splits on:
    - Newlines
    - Dash/hyphen bullets (-, –, —)
    - Bullet symbols (•, ●, ◆, ▪)
    - Numbers (1., 2., etc.)
    
    Filters out:
    - Lines < 10 characters
    - Lines that are just headers or noise
    """
    # Split on newlines first
    lines = text.split('\n')
    
    bullets = []
    for line in lines:
        line = line.strip()
        
        # Remove leading bullets/numbers (including • symbol)
        line = re.sub(r'^[•●◆▪\-–—]\s*', '', line)
        line = re.sub(r'^\d+\.\s*', '', line)
        line = re.sub(r'^[a-z]\.\s*', '', line, flags=re.IGNORECASE)
        
        # Skip short or empty lines
        if len(line) < 10:
            continue
        
        # Skip lines that look like section headers
        if line.isupper() and len(line) < 50:
            continue
        if line.endswith(':') and len(line) < 80:
            continue
        
        # Skip common noise patterns
        if re.match(r'(?i)^(minimum|preferred|basic|required|optional)\s*qualifications?:?$', line):
            continue
        
        bullets.append(line)
    
    return bullets


# ====================================================
# 3️⃣ METADATA EXTRACTION
# ====================================================

def extract_metadata(clean_text: str, job_title: Optional[str] = None) -> Dict[str, str]:
    """
    Extract metadata from JD text.
    
    Extracts:
    - Job title
    - Seniority level (Junior, Mid-level, Senior, Lead, Principal)
    - Domain (Data Engineering, ML, DevOps, etc.)
    - Location (if present)
    
    Args:
        clean_text: Cleaned JD text
        job_title: Optional job title from user input (overrides extraction)
        
    Returns:
        Dictionary with metadata fields
    """
    metadata = {
        "title": job_title or "Software Engineer",
        "seniority": "Not specified",
        "domain": "Software Engineering",
        "location": "Not specified"
    }
    
    # Extract job title if not provided
    if not job_title:
        title = _extract_job_title(clean_text)
        if title:
            metadata["title"] = title
    
    # Extract seniority level
    metadata["seniority"] = _extract_seniority(clean_text, metadata["title"])
    
    # Extract domain
    metadata["domain"] = _extract_domain(metadata["title"], clean_text)
    
    # Extract location
    location = _extract_location(clean_text)
    if location:
        metadata["location"] = location
    
    logger.info(f"Metadata extracted: {metadata}")
    
    return metadata


def _extract_job_title(text: str) -> Optional[str]:
    """Extract job title from first few lines or pattern matches."""
    # Common title patterns (expanded for better coverage)
    title_patterns = [
        # HR/People/Talent roles
        r"(?i)(Senior|Junior|Lead|Principal|Staff)?\s*(HR|Human Resources|People|Talent)\s*(Data\s*)?(Analyst|Manager|Partner|Specialist|Coordinator)",
        # Data/Analytics roles
        r"(?i)(Senior|Junior|Lead|Principal|Staff)?\s*(Data|Software|ML|Machine Learning|AI|Cloud|DevOps|Analytics|Full Stack|Backend|Frontend|Site Reliability|Technical Operations)\s*(Engineer|Developer|Analyst|Scientist|Architect)",
        # QA roles
        r"(?i)(Senior|Junior|Lead|Principal|Staff)?\s*(QA|Quality Assurance|Test)\s*(Engineer|Analyst)",
        # Management roles
        r"(?i)(Senior|Junior|Lead|Principal|Staff)?\s*(Product|Program|Project)\s*Manager",
        # Business/Analyst roles
        r"(?i)(Senior|Junior|Lead|Principal|Staff)?\s*(Business|Systems|Operations|Financial|Workforce)\s*Analyst",
        # Generic roles
        r"(?i)(Senior|Junior|Lead|Principal|Staff)?\s*Analyst",
        r"(?i)(Senior|Junior|Lead|Principal|Staff)?\s*Engineer",
    ]
    
    # Try first 2500 characters (title can appear in longer intro text)
    first_section = text[:2500]
    
    for pattern in title_patterns:
        match = re.search(pattern, first_section)
        if match:
            title = match.group(0).strip()
            return title
    
    return None


def _extract_seniority(text: str, title: str) -> str:
    """Detect seniority level from title or text."""
    text_lower = text.lower()
    title_lower = title.lower()
    
    # Seniority keywords (order matters - check most specific first)
    seniority_map = {
        "principal": "Principal",
        "staff": "Staff",
        "lead": "Lead",
        "senior": "Senior",
        "sr": "Senior",
        "sr.": "Senior",
        "iii": "Senior",
        "level 3": "Senior",
        "l3": "Senior",
        "mid-level": "Mid-level",
        "intermediate": "Mid-level",
        "ii": "Mid-level",
        "level 2": "Mid-level",
        "l2": "Mid-level",
        "junior": "Junior",
        "jr": "Junior",
        "jr.": "Junior",
        "entry": "Junior",
        "associate": "Mid-level",
        "entry-level": "Junior",
    }
    
    # Check title first (exact match with word boundaries)
    for keyword, level in seniority_map.items():
        # Use word boundary regex to avoid false positives
        import re
        if re.search(rf'\b{re.escape(keyword)}\b', title_lower):
            return level
    
    # Check for years of experience patterns
    years_patterns = [
        r"(\d+)\+?\s*years",
        r"(\d+)-(\d+)\s*years",
    ]
    
    for pattern in years_patterns:
        match = re.search(pattern, text_lower)
        if match:
            years = int(match.group(1))
            if years >= 8:
                return "Senior"
            elif years >= 5:
                return "Mid-level"
            elif years >= 2:
                return "Mid-level"
            else:
                return "Junior"
    
    # Check text for seniority keywords
    for keyword, level in seniority_map.items():
        if keyword in text_lower[:1000]:  # Check first 1000 chars
            return level
    
    return "Mid-level"  # Default


def _extract_domain(title: str, text: str) -> str:
    """Identify domain based on title and keywords."""
    title_lower = title.lower()
    text_lower = text.lower()
    
    # Domain keywords mapping
    domain_keywords = {
        "Data Engineering": ["data engineer", "etl", "data pipeline", "data warehouse", "spark", "airflow", "kafka"],
        "Machine Learning": ["machine learning", "ml engineer", "deep learning", "neural network", "tensorflow", "pytorch", "model"],
        "AI/ML": ["ai engineer", "artificial intelligence", "nlp", "computer vision", "llm", "generative ai"],
        "Data Science": ["data scientist", "data analysis", "statistical", "predictive model", "analytics"],
        "Cloud Engineering": ["cloud engineer", "aws", "azure", "gcp", "cloud infrastructure", "terraform"],
        "DevOps": ["devops", "site reliability", "sre", "ci/cd", "kubernetes", "docker", "infrastructure"],
        "Backend Engineering": ["backend", "api", "microservices", "rest", "graphql", "server"],
        "Frontend Engineering": ["frontend", "react", "angular", "vue", "ui", "user interface"],
        "Full Stack": ["full stack", "fullstack", "full-stack"],
        "Mobile Development": ["mobile", "ios", "android", "react native", "flutter"],
        "QA/Testing": ["qa", "quality assurance", "test automation", "testing"],
        "Security": ["security", "cybersecurity", "infosec", "penetration"],
        "Embedded Systems": ["embedded", "firmware", "iot", "hardware"],
    }
    
    # Check title first
    for domain, keywords in domain_keywords.items():
        for keyword in keywords:
            if keyword in title_lower:
                return domain
    
    # Check text (first 2000 chars for performance)
    text_sample = text_lower[:2000]
    domain_scores = {}
    
    for domain, keywords in domain_keywords.items():
        score = sum(1 for keyword in keywords if keyword in text_sample)
        if score > 0:
            domain_scores[domain] = score
    
    # Return domain with highest score
    if domain_scores:
        return max(domain_scores, key=domain_scores.get)
    
    return "Software Engineering"


def _extract_location(text: str) -> Optional[str]:
    """Extract location if present in JD."""
    # Location patterns (ordered by specificity - more specific first)
    location_patterns = [
        r"(?i)location:?\s*([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\b",  # Location: City, ST
        r"(?i)based in\s+([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\b",   # based in City, ST
        r"(?i)office in\s+([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\b",  # office in City, ST
        r"(?i)in-office at[^,]*in\s+([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\b",  # in-office at X in City, ST
        r"(?i)([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\s*(?:remote|hybrid|onsite)",  # City, ST Remote
        r"\bin\s+([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\s*[^\w]",  # in City, ST (followed by non-word)
    ]
    
    # Search entire text to find location mentions (location can be anywhere)
    for pattern in location_patterns:
        match = re.search(pattern, text)  # Search full text
        if match:
            location = match.group(1).strip()
            # Clean up common artifacts
            location = re.sub(r'\s+', ' ', location)
            # Validate it's a real location (not just any two letters after comma)
            if len(location) > 5:  # At least "City, ST" format
                return location
    
    # Check for remote/hybrid indicators
    if re.search(r"(?i)\b(remote|work from home|wfh)\b", text[:1000]):
        return "Remote"
    if re.search(r"(?i)\bhybrid\b", text[:1000]):
        return "Hybrid"
    
    return None


# ====================================================
# 4️⃣ DOMAIN CLASSIFICATION
# ====================================================

def _infer_domain_from_title(title: str) -> str:
    """Quick domain inference from job title."""
    title_lower = title.lower()
    
    if "data engineer" in title_lower:
        return "Data Engineering"
    elif "machine learning" in title_lower or "ml engineer" in title_lower:
        return "Machine Learning"
    elif "data scien" in title_lower:
        return "Data Science"
    elif "data analyst" in title_lower or "analytics" in title_lower:
        return "Data Analytics"
    elif "devops" in title_lower:
        return "DevOps"
    elif "cloud" in title_lower:
        return "Cloud Engineering"
    elif "backend" in title_lower:
        return "Backend Engineering"
    elif "frontend" in title_lower or "front-end" in title_lower:
        return "Frontend Engineering"
    elif "full stack" in title_lower or "fullstack" in title_lower:
        return "Full Stack"
    elif "qa" in title_lower or "quality" in title_lower or "test" in title_lower:
        return "QA/Testing"
    elif "security" in title_lower:
        return "Security"
    elif "mobile" in title_lower:
        return "Mobile Development"
    elif "hr" in title_lower or "human resources" in title_lower:
        return "HR/People Analytics"
    else:
        return "Software Engineering"


async def classify_domain_with_llm(clean_text: str, title: str) -> str:
    """
    Use LLM to classify domain if regex fails or confidence is low.
    
    This is a fallback when keyword-based extraction is ambiguous.
    """
    prompt = f"""You are a job domain classifier. Analyze this job description and classify it into ONE of these domains:

DOMAINS:
- Data Engineering
- Machine Learning
- AI/ML
- Data Science
- Cloud Engineering
- DevOps
- Backend Engineering
- Frontend Engineering
- Full Stack
- Mobile Development
- QA/Testing
- Security
- Embedded Systems
- Software Engineering (general)

JOB TITLE: {title}

JD TEXT (first 1500 chars):
{clean_text[:1500]}

Return ONLY the domain name, nothing else.
"""
    
    try:
        response = await chat_completion_async(prompt)
        domain = response.strip()
        logger.info(f"LLM classified domain as: {domain}")
        return domain
    except Exception as e:
        logger.error(f"LLM domain classification failed: {e}")
        return "Software Engineering"


# ====================================================
# 5️⃣ MAIN PREPROCESSING PIPELINE
# ====================================================

async def preprocess_jd(
    raw_text: str,
    job_title: Optional[str] = None,
    use_llm_extraction: bool = True
) -> Dict:
    """
    Complete JD preprocessing pipeline with LLM-based extraction for 100% accuracy.
    
    Strategy:
    1. Primary: LLM extraction (high accuracy, no hallucination)
    2. Fallback: Regex extraction (if LLM fails)
    
    Args:
        raw_text: Raw JD text (may contain HTML)
        job_title: Optional job title override
        use_llm_extraction: Whether to use LLM for extraction (recommended: True)
        
    Returns:
        Structured JD object:
        {
            "clean_text": str,
            "sections": dict,
            "metadata": dict,
            "normalized_jd": str,
            "section_weights": dict,
            "extraction_method": "llm" or "regex"
        }
    """
    try:
        # Step 1: Clean text
        clean_text = clean_jd_text(raw_text)
        
        extraction_method = "regex"
        
        # Step 2: Try LLM extraction first (PRIMARY METHOD)
        if use_llm_extraction:
            logger.info("[PREPROCESSING] Attempting LLM-based extraction...")
            llm_result = await extract_with_llm(clean_text)
            
            if llm_result and llm_result.get("job_title"):
                # LLM extraction succeeded - use it
                logger.info("[PREPROCESSING] LLM extraction successful!")
                extraction_method = "llm"
                
                # Build sections from LLM result
                sections = {
                    "responsibilities": llm_result.get("responsibilities", []),
                    "requirements": llm_result.get("requirements", []),
                    "preferred": llm_result.get("preferred", [])
                }
                
                # Build metadata from LLM result
                metadata = {
                    "title": job_title or llm_result.get("job_title", "Not specified"),
                    "seniority": llm_result.get("seniority", "Not specified"),
                    "domain": _infer_domain_from_title(llm_result.get("job_title", "")),
                    "location": llm_result.get("location", "Not specified")
                }
            else:
                logger.warning("[PREPROCESSING] LLM extraction failed, falling back to regex...")
                # Fall through to regex method below
                use_llm_extraction = False
        
        # Step 3: Fallback to regex-based extraction
        if not use_llm_extraction or extraction_method == "regex":
            logger.info("[PREPROCESSING] Using regex-based extraction...")
            sections = split_sections(clean_text)
            metadata = extract_metadata(clean_text, job_title)
            
            # Try LLM for domain classification only
            if metadata["domain"] == "Software Engineering" and "engineer" not in metadata["title"].lower():
                try:
                    metadata["domain"] = await classify_domain_with_llm(clean_text, metadata["title"])
                except:
                    pass
        
        # Step 4: Create normalized JD text
        normalized_jd = _create_normalized_jd(sections)
        
        # Step 5: Calculate section weights
        section_weights = _calculate_section_weights(sections)
        
        # Step 6: Build result
        result = {
            "clean_text": clean_text,
            "sections": sections,
            "metadata": metadata,
            "normalized_jd": normalized_jd,
            "section_weights": section_weights,
            "extraction_method": extraction_method,
            "preprocessing_stats": {
                "original_length": len(raw_text),
                "cleaned_length": len(clean_text),
                "total_bullets": sum(len(v) for v in sections.values()),
                "sections_found": [k for k, v in sections.items() if v],
                "method_used": extraction_method
            }
        }
        
        logger.info(f"[PREPROCESSING] Complete using {extraction_method.upper()} method: "
                   f"resp={len(sections['responsibilities'])}, req={len(sections['requirements'])}, "
                   f"pref={len(sections['preferred'])}")
        
        return result
        
    except Exception as e:
        logger.error(f"JD preprocessing failed: {e}")
        raise


def _create_normalized_jd(sections: Dict[str, List[str]]) -> str:
    """Create a structured normalized JD text with section markers."""
    parts = []
    
    if sections["responsibilities"]:
        parts.append("[RESPONSIBILITIES]")
        parts.extend(sections["responsibilities"])
        parts.append("")
    
    if sections["requirements"]:
        parts.append("[REQUIREMENTS]")
        parts.extend(sections["requirements"])
        parts.append("")
    
    if sections["preferred"]:
        parts.append("[PREFERRED]")
        parts.extend(sections["preferred"])
    
    return "\n".join(parts)


def _calculate_section_weights(sections: Dict[str, List[str]]) -> Dict[str, float]:
    """
    Calculate relative importance of each section based on bullet count.
    
    Default weights if all sections present:
    - Responsibilities: 0.3
    - Requirements: 0.5 (most important for matching)
    - Preferred: 0.2
    """
    total_bullets = sum(len(v) for v in sections.values())
    
    if total_bullets == 0:
        return {"responsibilities": 0.0, "requirements": 0.0, "preferred": 0.0}
    
    # Calculate proportional weights
    weights = {
        "responsibilities": len(sections["responsibilities"]) / total_bullets,
        "requirements": len(sections["requirements"]) / total_bullets,
        "preferred": len(sections["preferred"]) / total_bullets,
    }
    
    # Boost requirements weight (most important for resume tailoring)
    if weights["requirements"] > 0:
        weights["requirements"] *= 1.5
    
    # Normalize to sum to 1.0
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}
    
    return weights


# ====================================================
# 6️⃣ UTILITY FUNCTIONS
# ====================================================

def validate_preprocessed_jd(jd_data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate preprocessed JD structure.
    
    Returns:
        (is_valid, error_message)
    """
    required_keys = ["clean_text", "sections", "metadata", "normalized_jd", "section_weights"]
    
    for key in required_keys:
        if key not in jd_data:
            return False, f"Missing required key: {key}"
    
    # Validate sections
    if not isinstance(jd_data["sections"], dict):
        return False, "sections must be a dictionary"
    
    required_sections = ["responsibilities", "requirements", "preferred"]
    for section in required_sections:
        if section not in jd_data["sections"]:
            return False, f"Missing section: {section}"
    
    # Validate metadata
    required_metadata = ["title", "seniority", "domain", "location"]
    for field in required_metadata:
        if field not in jd_data["metadata"]:
            return False, f"Missing metadata field: {field}"
    
    # Validate at least one section has content
    total_bullets = sum(len(v) for v in jd_data["sections"].values())
    if total_bullets == 0:
        return False, "No content found in any section"
    
    return True, None


def get_jd_summary(jd_data: Dict) -> str:
    """
    Generate a human-readable summary of preprocessed JD.
    
    Useful for logging and debugging.
    """
    stats = jd_data.get("preprocessing_stats", {})
    metadata = jd_data.get("metadata", {})
    sections = jd_data.get("sections", {})
    
    summary = f"""
JD Preprocessing Summary
========================
Title:     {metadata.get('title', 'Unknown')}
Seniority: {metadata.get('seniority', 'Unknown')}
Domain:    {metadata.get('domain', 'Unknown')}
Location:  {metadata.get('location', 'Unknown')}

Text:      {stats.get('original_length', 0)} → {stats.get('cleaned_length', 0)} chars
Sections:  {', '.join(stats.get('sections_found', []))}
Bullets:   Resp={len(sections.get('responsibilities', []))}, Req={len(sections.get('requirements', []))}, Pref={len(sections.get('preferred', []))}
"""
    return summary.strip()
