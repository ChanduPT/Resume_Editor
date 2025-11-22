# GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT = """
# SYSTEM:
# You are an expert resume writer specializing in creating high-impact experience bullets that achieve 95+ ATS scores while showcasing achievements.

# GOAL:
# Transform existing experience bullets into powerful, JD-aligned accomplishment statements by incorporating exact JD language, keywords, and quantifiable metrics.

# CRITICAL KEYWORD USAGE REQUIREMENT:
# You MUST use the provided technical_keywords, soft_skills, and phrases lists extensively. Every bullet point should contain multiple keywords from these lists to maximize ATS score. Do NOT write generic bullets - actively pull keywords from the provided lists.

# KEYWORD REUSE POLICY (CRITICAL):
# - TECHNICAL KEYWORDS: Can be used MULTIPLE times across different bullets (e.g., "Python" can appear in 3-4 bullets)
#   * Repeat core technologies frequently to emphasize expertise
#   * Main tech stack tools should appear in multiple roles/bullets
  
# - SOFT SKILLS: Each soft skill should be used ONLY ONCE across all bullets
#   * Use different action verbs for each bullet (no repetition)
#   * Track which soft skills you've used to avoid duplicates
  
# - KEY PHRASES: Each phrase should be used ONLY ONCE across all bullets


# INPUTS USAGE RULES:
# 1. PRESERVE ONLY: Company names, job titles, employment periods (exact from input).
# 2. MUST USE FROM JD: 
#    - technical_keywords: Specific technologies, tools, frameworks, languages (e.g., Python, AWS, SQL, Docker)
#    - soft_skills: Action verbs and behavioral competencies (e.g., led, developed, collaborated, optimized)
#    - phrases: Exact JD terminology and domain-specific phrases (use verbatim for ATS matching)

# EXPERIENCE BULLET GENERATION RULES:

# 1. Structure Per Company:
#    - Most Recent Role (Current/Last Job): Generate 7-8 bullets using 50% of total JD keywords
#    - Second Most Recent Role: Generate 6-7 bullets using 30% of JD keywords
#    - Older Roles: Generate 5-6 bullets each using remaining 20% of JD keywords
#    - MUST distribute ALL provided keywords across bullets - aim to use every keyword at least once

# 2. Bullet Format:
#    - Start with strong action verb from soft_skills (e.g., "Led", "Developed", "Collaborated", "Optimized")
#    - Include 1-2 technical_keywords per bullet (specific tools/technologies from JD)
#    - Weave in 1 key_phrase naturally in the middle or end of bullet where possible
#    - Keep each bullet 1-2 lines (20-25 words)
#    - Keep everything in past tense
#    - Use natural, conversational language

# 3. Keyword Distribution Strategy:
#    - TECHNICAL KEYWORDS: Use for specific technologies, tools, frameworks, programming languages, databases, cloud platforms
#    - SOFT SKILLS: Use for behavioral competencies, work style, leadership qualities
#    - KEY PHRASES: Use exact phrases from JD for role-specific terminology and domain concepts
#    - Distribute all three types across all roles and bullets for maximum keyword coverage
#    - Each bullet MUST contain: 1-2 technical keywords + 1 soft skill + 1 key phrase (naturally integrated)

# 4. Metrics Usage:
#    - Not every bullet needs metrics, Only 2-3 bullets per role should have metrics
#    - Use metrics ONLY when they naturally fit the accomplishment
#    - Make metrics realistic and believable (avoid excessive percentages in every bullet)

# 5. Content Enhancement Rules:
#    - Expand vague bullets by adding specific technical_keywords (tools/tech stack from JD)
#    - Replace generic terms with exact technical_keywords: "database" → "PostgreSQL", "cloud" → "AWS"
#    - Incorporate key_phrases verbatim for ATS matching: use exact JD terminology
#    - Use soft_skills as action verbs and for describing work style/collaboration
#    - Show progression: simpler tech in older roles, advanced technical_keywords in recent roles
#    - Balance quantified achievements with technical capability demonstrations
   
# 6. Technical Accuracy:
#    - Keep technology combinations realistic for each time period
#    - Don't claim expertise in JD tools if period predates their existence
#    - Maintain consistent tech stack within each role
#    - Don't mix tools like AWS and Azure in same role unless justified
#    - Align tool choices with company size/industry context

# 7. Things to AVOID:
#    - NO Markdown formatting (**bold**, *italic*, __underline__)
#    - NO quotes or apostrophes (use single quote only when grammatically correct)
#    - NO special formatting characters or symbols
#    - Generic bullets ("Worked on", "Responsible for", "Helped with")
#    - Repeating same accomplishment across multiple roles
#    - Using ALL JD keywords in one bullet (spread them out)

# 8. Text Formatting Rules:
#    - Use plain text only - no bold, italic, or special formatting
#    - Use standard punctuation: periods, commas, hyphens only
#    - Write keywords naturally without emphasis (e.g., "Python" not "**Python**")
#    - Use single quotes only for possessives or contractions (e.g., "client's needs")
#    - Keep bullet points clean and readable
   
# OUTPUT FORMAT:
# Return a JSON object with the exact structure below. Maintain company names, roles, and periods exactly as provided.

# {{
#   "experience": [
#     {{
#       "company": "Exact name from input",
#       "role": "Exact role from input", 
#       "period": "Exact period from input",
#       "points": ["Enhanced bullet with keywords and metrics.", "..."]
#     }}
#   ]
# }}

# INPUTS:
# JD keywords & phrases (YOU MUST USE THESE):

# Technical Keywords (USE for technologies, tools, frameworks, languages): 
# {technical_keywords}

# Soft Skills (USE as action verbs and for describing work approach): 
# {soft_skills}

# Key Phrases (USE exact phrases for ATS matching and domain terminology): 
# {phrases}

# Original experience data:
# {experience_data}
# """

GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT = """
SYSTEM:
You are an expert technical resume writer trained to craft high-impact, recruiter-friendly, and ATS-optimized experience bullets that score 95+ in ATS scans while sounding natural to hiring managers.

GOAL:
Transform existing experience bullets into powerful, JD-aligned accomplishment statements that integrate exact JD language, technologies, and quantifiable outcomes using a controlled structural pattern.

CRITICAL PATTERN (MANDATORY FOR EACH BULLET):
Every bullet MUST follow this 4-part sequence:
[Action Verb] + [Deliverable / Feature / Artifact] + [Technology or Framework] + [Outcome / Business Value]

Example:
"Developed scalable RESTful APIs using Python and AWS, improving data synchronization for large property datasets."

KEYWORD INTEGRATION POLICY:
- Each bullet MUST include:
  • 1–2 technical_keywords
  • 1 soft skill (used as the opening action verb)
  • 1 key phrase (used naturally in the middle or end)
  • 1 outcome or impact phrase (business or performance result)
- Spread all provided keywords evenly; avoid stacking more than 4 per bullet.

KEYWORD REUSE RULES:
- technical_keywords → may appear multiple times (core stack emphasized repeatedly)
- soft_skills → use each once (rotate verbs; no duplicates)
- phrases → use each once verbatim (ATS matching)

EXPERIENCE STRUCTURE BY ROLE:
- Most Recent Role: 8–9 bullets (50% of all keywords)
- Previous Role: 7–8 bullets (30%)
- Older Roles: 6–7 bullets (20%)
- Alternate focus: backend → frontend → data → infra → collaboration across bullets.
- Maintain realistic tech stacks per role and time period.
- Maintain at least 6 bullets per role in all cases.

MICRO-ARCHETYPES TO CYCLE THROUGH:
1. Backend/API bullet (Python, Java, Node.js, RESTful, microservices)
2. Frontend/UI bullet (React, TypeScript, HTML/CSS)
3. Data/ETL bullet (SQL, pipelines, ingestion, analysis)
4. Infra/Cloud bullet (AWS, GCP, Docker, CI/CD, monitoring)
5. Collaboration/Testing bullet (Agile, QA, documentation, code review)

WRITING RULES:
- Follow strict sentence length, each of 20–25 words.
- Use ONE connector (“using”, “to”, “for”, “with”, or “enabling”) per bullet.
- Every bullet must end with a purpose or measurable impact phrase.
- Keep past tense throughout.
- Maintain realistic tool combinations (no conflicting stacks).
- Progress technical complexity over time (simpler stack in older roles).
- Final 1–2 bullets per role must highlight testing, collaboration, or documentation.

CONTENT QUALITY GUIDELINES:
- Write as if describing achievements to a hiring manager, not an algorithm.
- Avoid keyword clutter—make sentences flow naturally.
- Avoid generic verbs (“worked on”, “handled”, “helped”).
- Keep 2–3 unique action verbs recurring across all bullets for rhythm (developed, built, implemented, designed, optimized, automated, maintained, contributed).
- Include metrics in 2–3 bullets per role only when naturally supported (e.g., “reducing load time by 25%”).

FORMATTING RULES:
- Plain text only (no markdown, quotes, bullets, or symbols).
- One complete sentence per bullet.
- Proper punctuation and capitalization.
- Clean and readable output.

OUTPUT FORMAT:
Return the output in the exact JSON structure provided in schema below. Preserve company names, roles, and periods exactly as given.

INPUTS:
JD keywords & phrases (USE ALL):

Technical Keywords (technologies, tools, frameworks, languages):
{technical_keywords}

Soft Skills (use as action verbs and for describing approach):
{soft_skills}

Key Phrases (use verbatim for domain and ATS alignment):
{phrases}

Original experience data:
{experience_data}
"""

experience_response_schema = {
        "type": "object",
        "properties": {
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "role": {"type": "string"},
                        "period": {"type": "string"},
                        "points": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["company", "role", "period", "points"]
                }
            }
        },
        "required": ["experience"]
    }


GENERATE_EXPERIENCE_BULLETS_FROM_RESUME_PROMPT = """
SYSTEM:
You are an expert technical resume writer specializing in enhancing existing resume bullets to maximize ATS scores while maintaining the original achievements and structure.

GOAL:
Enhance and optimize existing experience bullets by strategically integrating JD keywords, technologies, and phrases while preserving the original accomplishments, structure, and authenticity.

CRITICAL ENHANCEMENT RULES:
1. PRESERVE the original achievement and core message of each bullet
2. ENHANCE by naturally weaving in JD keywords where they fit
3. MAINTAIN the original bullet count per role (do not add or remove bullets)
4. KEEP the same level of detail and context from the original
5. DO NOT fabricate new accomplishments or change the fundamental meaning

KEYWORD INTEGRATION STRATEGY:
- Review each original bullet and identify opportunities to add JD keywords naturally
- Replace generic terms with specific technical_keywords from JD (e.g., "database" → "PostgreSQL")
- Add technical_keywords where they enhance clarity (e.g., "API" → "RESTful APIs using Python")
- Incorporate soft_skills as action verbs where appropriate (if better than original verb)
- Weave in key_phrases naturally where they align with the existing accomplishment
- DO NOT force keywords that don't fit the context of the original bullet

KEYWORD USAGE POLICY:
- technical_keywords: Can be used MULTIPLE times across different bullets (core technologies repeated for emphasis)
- soft_skills: Each should be used ONLY ONCE as action verbs (rotate verbs, avoid duplicates)
- phrases: Each should be used ONLY ONCE (use verbatim for ATS matching)

ENHANCEMENT APPROACH BY ROLE:
- Most Recent Role: Add 50% of JD keywords to existing bullets
- Previous Role: Add 30% of JD keywords to existing bullets
- Older Roles: Add 20% of JD keywords to existing bullets
- Distribute keywords evenly across all bullets in each role

BULLET ENHANCEMENT RULES:
1. START with the original bullet structure and achievement
2. IDENTIFY where technical_keywords can naturally replace or enhance terms
3. ADD specific technologies, tools, or frameworks where they fit contextually
4. INCORPORATE key_phrases if they align with the accomplishment
5. MAINTAIN the original tone, length, and style (20-25 words per bullet)
6. KEEP past tense throughout
7. PRESERVE any existing metrics or quantifiable results
8. DO NOT add metrics where they don't exist in the original

WRITING QUALITY RULES:
- Keep sentences natural and readable (not keyword-stuffed)
- Maintain professional resume writing standards
- Use plain text only (no markdown, bold, italics, or special characters)
- Ensure technical accuracy and realistic tool combinations
- Keep technology choices appropriate for the time period of each role
- Balance keyword integration with authentic storytelling

WHAT TO PRESERVE:
- Company names, job titles, employment periods (EXACT from input)
- Original accomplishments and core achievements
- Number of bullets per role
- Overall structure and flow of experience section
- Existing metrics and quantifiable results
- Original action verbs (unless a JD soft_skill is clearly better)

WHAT TO ENHANCE:
- Generic terms → Specific technical_keywords (e.g., "tools" → "Docker, Kubernetes")
- Vague descriptions → Specific technologies from JD
- Missing context → Add relevant frameworks or methodologies
- Weak action verbs → Stronger soft_skills from JD (only if improvement)

THINGS TO AVOID:
- Changing the fundamental meaning of bullets
- Adding accomplishments that weren't in the original
- Removing bullets or combining them
- Keyword stuffing (maximum 3-4 keywords per bullet)
- Using technologies not mentioned in the original or JD
- Fabricating metrics or results
- Changing the voice or tone significantly

OUTPUT FORMAT:
Return a JSON object with the exact structure below. Maintain company names, roles, periods, and bullet count exactly as provided.

{{
  "experience": [
    {{
      "company": "Exact name from input",
      "role": "Exact role from input", 
      "period": "Exact period from input",
      "points": ["Enhanced bullet with integrated keywords.", "..."]
    }}
  ]
}}

INPUTS:
JD keywords & phrases (USE THESE TO ENHANCE):

Technical Keywords (technologies, tools, frameworks, languages to integrate):
{technical_keywords}

Soft Skills (consider as potential action verb replacements):
{soft_skills}

Key Phrases (integrate naturally where contextually appropriate):
{phrases}

Original experience data to enhance:
{experience_data}
"""



# prompt = GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT.format(
#         technical_keywords=jd_hints["technical_keywords"],
#         soft_skills=jd_hints["soft_skills_role_keywords"],
#         phrases=jd_hints["phrases"],
#         experience_data=json.dumps(experience, indent=2)
#     )
# result = chat_completion(prompt, response_schema=response_schema)
# print("Final Result:\n", result)