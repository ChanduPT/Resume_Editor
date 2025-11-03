# app/prompts.py

REWRITE_SECTION_PROMPT = """
SYSTEM ROLE:
You are a senior technical resume editor and recruiter-level language expert.

GOAL:
Rewrite the given RESUME SECTION so that it aligns naturally and credibly with the job description (JD) hints below.

INSTRUCTIONS:
- Read and interpret the JD hints deeply — understand what kind of professional the role demands.
- Update the section to reflect relevant **tools, technologies, methodologies, and responsibilities** mentioned in the JD.
- Replace or rephrase irrelevant or outdated terms with JD-aligned equivalents **only if plausible** given the original context.
- Add missing but contextually justifiable JD keywords (don’t fabricate achievements or skills).
- Preserve truthfulness, chronology, employer, and tone.
- Prioritize clear, active, outcome-oriented phrasing using strong verbs.
- Output **only the rewritten section text**, no commentary or headers.

JD (condensed hints):
{jd_hints}

SECTION (original):
{section_text}
"""


JD_HINTS_PROMPT = """
You are an expert in analyzing job descriptions for any technical or analytical role.

Carefully analyze the job description below and extract TWO types of information:
1. Important keywords and terms
2. Key phrases and sentences that should be reflected in the resume

PART 1 - Keywords/Terms to extract:
- Programming languages, frameworks, libraries, APIs
- Cloud, DevOps, and infrastructure tools
- Databases, ETL tools, data warehouses, pipelines
- BI, analytics, ML, and visualization tools
- Version control, SDLC, CI/CD, testing, and deployment practices
- Agile, Scrum, and collaboration tools
- Business domains (finance, healthcare, e-commerce, etc.)
- Certifications and compliance standards (AWS Certified, HIPAA, GDPR, PMP, etc.)
- Core responsibilities and action verbs (design, develop, automate, optimize, collaborate, monitor, deploy)
- Soft skills and leadership keywords (communication, teamwork, mentoring, stakeholder management)

PART 2 - Phrases to extract:
- Exact responsibilities or requirements statements
- Project or achievement descriptions
- Technical workflow or process descriptions
- Key performance indicators or metrics mentioned
- Specific domain expertise descriptions
- Team collaboration and leadership descriptions

JD:
{jd_text}

Return the analysis in this format:
KEYWORDS: comma-separated list of all extracted keywords and terms
PHRASES: bullet-pointed list of exact, relevant phrases from the JD that could be adapted into resume bullets
"""


SCORING_PROMPT_JSON = """
STRICT INSTRUCTION: Output ONLY valid JSON. No explanations or markdown.
Return the JSON inside triple backticks.
Do not include any other text or formatting.

```json

{
  "match_score": 0,
  "verdict": "Strong|Moderate|Weak",
  "summary": "string",
  "section_updates": [
    {
      "section": "Summary|Skills|Experience|Projects|Education|Certifications",
      "content_type": "bullet_array|text_block",
      "existing": "string",
      "update": {
        "bullets": ["Complete sentence 1.", "Complete sentence 2."],
        "text": "string"
      },
      "reason": "string"
    }
  ],
  "final_recommendation": "string"
}
```

RULES FOR JSON GENERATION:
- No extra keys, no markdown, no prose outside JSON.
- Use concise text that can be pasted into a resume.
- If content is in bullet format, use "content_type": "bullet_array"
- Each bullet must be a complete sentence ending with a period.
- Keep bullet points consistent in length and detail level.

Technical Accuracy Rules:
1. Technology Stack Consistency:
   - Don't mix competing technologies (e.g., Tableau vs Power BI)
   - Don't suggest multiple cloud platforms unless explicitly required
   - Keep database choices consistent within roles
   
2. Company Size/Type Appropriateness:
   - Suggest enterprise tools for large companies
   - Suggest open-source/flexible tools for startups
   - Match tool suggestions to company's known tech stack

3. Role-Appropriate Tools:
   - Suggest tools that match the seniority level
   - Keep tool combinations realistic for the role
   - Maintain consistency with the industry standard

4. Timeline Consistency:
   - Only suggest technologies that existed at the time
   - Consider version compatibility between tools
   - Account for technology evolution in older roles

JD:
{jd_text}

RESUME:
{resume_text}
"""

APPLY_EDITS_PROMPT = """
SYSTEM:
You are a precise technical resume editor with expertise in technology stack validation.

GOAL:
Apply the supplied edit directives to the given resume SECTION. Make the section align with the JD while ensuring technical accuracy:

EDITING RULES:
1. Content Alignment:
   - Replace: If 'existing_not_relevant' exists, use 'replace_with'
   - Add: Integrate new content naturally, not as keyword lists
   - Preserve: Keep truthful chronology, employers, and dates
   - Maintain: Keep similar tone and length unless clarity needs change

2. Technical Accuracy:
   - Use consistent technology choices within each role
   - Don't mix competing platforms (e.g., Tableau OR Power BI)
   - Ensure tool combinations make sense for company size/type
   - Keep technology timeline historically accurate
   - Maintain consistent cloud/database/framework choices

3. Reality Check:
   - Verify technology combinations are realistic
   - Ensure tools match company's known tech stack
   - Keep skill claims proportional to role/experience
   - Maintain reasonable project scope and impact

4. Version Compatibility:
   - Keep framework versions compatible
   - Ensure database versions align
   - Match cloud service versions to timeline

Output ONLY the final section text. No explanations.

INPUTS
JD hints (keywords): {jd_hints}

Original section:
<<<SECTION_START>>>
{section_text}
<<<SECTION_END>>>

Edit directives for this section (JSON array):
<<<EDITS_START>>>
{section_edits_json}
<<<EDITS_END>>>
"""

BALANCE_BULLETS_PROMPT = """
You are a senior technical recruiter reviewing an EXPERIENCE section.

INPUTS:
- JD key points (80%) below describe what the employer expects.
- Resume context (20%) below shows current bullets.

JD focus (80%):
{jd_hints}

Resume context (20%):
{section_text}

GOAL:
1. Produce 6–8 concise, metric-driven bullets.
2. 80% of bullets should incorporate JD keywords, technologies, or verbs.
3. 20% may retain resume context if related to JD.
4. Merge duplicates, remove filler, keep realistic scale.
5. Ensure technical accuracy and realism:
   - Don't mix competing technologies (e.g., not both Tableau AND Power BI)
   - Use the most relevant tool for the company/role
   - Maintain consistent technology stacks within roles
   - Avoid unrealistic combinations of tools
6. Format output strictly:
   - Each bullet must end with a period
   - No markdown or special formatting
   - No empty lines between bullets
   - Keep each bullet to 1-2 lines maximum
   - Use consistent punctuation throughout.

CRITICAL RULES:
- Keep claims realistic and focused
- Choose ONE primary tool when alternatives exist (e.g., Tableau OR Power BI, not both)
- Ensure technology combinations make sense for the role and company size
- Maintain consistency in tech stack across bullets within the same role
- Don't dilute impact by listing too many alternative tools


OUTPUT FORMAT (IMPORTANT):
Your final output must **only** contain the bullet points, each starting with a single dash followed by a space (`- `).  
Example:

- Designed and deployed Spring Boot microservices on AWS EKS, boosting uptime by 40%.
- Developed REST APIs for policy and CRM integrations, reducing latency by 35%.
- Implemented CI/CD pipelines with Jenkins and Docker, improving release efficiency by 30%.

Do not number the bullets, do not use any extra headers or labels like "Updated Experience:" — only output the bullet points exactly as shown above.
"""


# New prompt to parse experience section into JSON
PARSE_EXPERIENCE_PROMPT = """
You are an expert resume parser. Convert the experience section into structured JSON.

STRICT RULES:
1. Return ONLY valid JSON array - no explanatory text
2. Each object represents one job role
3. Create separate objects for different titles/roles at same company
4. Every bullet point must be a complete sentence ending with a period
5. Do not invent or modify content - parse exactly as provided
6. Do not add formatting or markdown

REQUIRED SCHEMA:
{
  "company": "Full company name",
  "title": "Job title or role",
  "dates": "Employment duration",
  "bullets": [
    "Complete sentence describing responsibility or achievement.",
    "Another complete sentence about the role."
  ]
}

Input experience text:
---
{experience_text}
---

Here is the experience section text:
---
{experience_text}
---

Respond ONLY with the JSON list of experiences. Do not include any introductory text or markdown formatting.
The output should be a raw JSON array.
"""

PARSE_SKILLS_PROMPT = """
You are an expert resume parser. Your task is to convert the "Skills" section of a resume into a structured JSON object.
Group related items under appropriate category headers (e.g., "Languages", "Cloud", "Databases", "Tools").
Each category should be a key, and the value should be a list of strings.

Here is the skills section text:
---
{skills_text}
---

Respond ONLY with the JSON object for the skills. Do not include any introductory text or markdown formatting.
The output should be a raw JSON object.
Output format:
{{
  "CategoryName": ["Skill1", "Skill2"],
  "CategoryName2": ["Skill3", "Skill4"]
}}

Example:
{{
  "Languages": ["Python", "Java", "JavaScript"],
  "Cloud": ["AWS", "Azure", "GCP"]
}}
"""


GENERATE_FROM_JD_PROMPT = """
SYSTEM:
You are an expert resume content generator focused on exact JD alignment.

GOAL:
Generate completely new content based on the JD while preserving only the structural elements from the original resume (company names, roles, dates).

INPUTS USAGE RULES:
1. From Resume - PRESERVE ONLY:
   - Company names and employment dates
   - Job titles/roles
   - Total years of experience
   - Everything else should be newly generated

2. From JD - USE EXTENSIVELY:
   - All technical keywords and tools
   - Exact phrases and responsibilities
   - Projects and workflows described
   - Performance metrics and KPIs
   - Domain terminology
   - Required skills and competencies

GENERATION RULES:
1. Content Creation:
   - Generate completely new bullets/content using JD keywords and phrases
   - Each bullet must include at least 2-3 keywords/phrases from JD
   - Include specific metrics and achievements (35%, 2x, etc.)
   - Focus on JD's primary requirements in most recent roles
   - Demonstrate progression of skills across roles

2. Technical Accuracy:
   - Use exact technical terms from JD
   - Keep technology combinations realistic for each time period
   - Maintain consistent tech stack within each role
   - Align tool choices with company size/industry

3. Structure Rules:
   - Generate 6-8 bullets per role
   - Each bullet must be a complete sentence ending with period
   - Start with strong action verbs
   - Include measurable impacts
   - Keep each bullet 1-2 lines maximum

4. Priority Order for Recent Roles:
   - Critical JD requirements (40% of bullets)
   - Technical skills & tools (30% of bullets)
   - Soft skills & leadership (20% of bullets)
   - Domain knowledge (10% of bullets)

Output ONLY the final section text. No explanations.

INPUTS
JD keywords & phrases:
<<<JD_START>>>
{jd_hints}
<<<JD_END>>>

Original section (preserve only structure):
<<<SECTION_START>>>
{section_text}
<<<SECTION_END>>>

Edit directives:
<<<EDITS_START>>>
{section_edits_json}
<<<EDITS_END>>>
"""


ORGANIZE_SKILLS_PROMPT = """
You are an expert technical knowledge organizer.

Task:
Take the following JSON of raw skills grouped loosely by category.
Your job is to deeply understand each skill and reorganize them into a clean, structured JSON
that groups related items together based on their function or purpose.

Instructions:
- Analyze the meaning of each skill (programming language, framework, cloud service, database, tool, library, methodology, etc.).
- Create broad, logical groupings — avoid over-fragmenting into too many subcategories.
- **CONSOLIDATE related skills into single categories** (e.g., combine "Data Engineering", "Data Processing", "Databases", "RDBMS" into just "Databases & Data Processing").
- **Limit to maximum 6-8 top-level categories** to keep skills section concise and readable.
- You may introduce new categories or merge existing ones if appropriate.
- Remove duplicates, fix inconsistent naming, and sort alphabetically within each list.
- The output **must be valid JSON only**, with no extra text.
- **Prefer broader categories over narrow ones** (e.g., use "Cloud & Infrastructure" instead of separate "Cloud Platforms" and "Infrastructure").
- Remove keywords that are not technical skills or tools (e.g., soft skills, methodologies) unless they are critical to the role.

Recommended category consolidation:
- Combine: Data Engineering, Data Processing, ETL, Databases, RDBMS, NoSQL → "Databases & Data Platforms"
- Combine: Cloud, Infrastructure, Containerization → "Cloud & Infrastructure"
- Combine: CI/CD, DevOps, Version Control → "DevOps & Version Control"
- Combine: BI Tools, Visualization, Analytics → "Analytics & Visualization"
- Combine: Testing, QA, Debugging → "Testing & Quality Assurance"

After grouping, **order the top-level categories logically** in this priority (if applicable):
   1. Programming Languages
   2. Frameworks & Libraries
   3. Cloud & Infrastructure
   4. Databases & Data Platforms
   5. Analytics & Visualization
   6. DevOps & Version Control
   7. Testing & Quality Assurance
   8. Methodologies & Practices

Example input:
{{
  "Programming Languages": ["Python", "SQL"],
  "Data Engineering": ["Airflow", "Spark"],
  "Databases": ["PostgreSQL", "MongoDB"],
  "RDBMS": ["MySQL"],
  "Cloud": ["AWS"],
  "Containers": ["Docker"],
  "ML": ["TensorFlow"]
}}

Example output (CONSOLIDATED):
{{
  "Programming Languages": ["Python", "SQL"],
  "Frameworks & Libraries": ["Spark", "TensorFlow"],
  "Cloud & Infrastructure": ["AWS", "Docker"],
  "Databases & Data Platforms": ["Airflow", "MongoDB", "MySQL", "PostgreSQL"]
}}

Now reorganize the following skills JSON with MAXIMUM 6-8 broad categories:

{skills_json}
"""



# ORGANIZE_SKILLS_PROMPT = """
# You are an expert technical knowledge organizer.

# Task:
# Take the following JSON of raw skills grouped loosely by category.
# Your job is to deeply understand each skill and reorganize them into a clean, structured JSON
# that groups related items together based on their function or purpose.

# Instructions:
# - Analyze the meaning of each skill (programming language, framework, cloud service, database, tool, library, methodology, etc.).
# - Create logical, human-readable groupings — name the categories yourself based on what makes sense semantically.
# - You may introduce new categories or merge existing ones if appropriate.
# - Remove duplicates, fix inconsistent naming, and sort alphabetically within each list.
# - The output **must be valid JSON only**, with no extra text.
# - After grouping, **order the top-level categories logically** in this priority (if applicable):
#    1. Programming Languages
#    2. Tools & Frameworks
#    3. Cloud / Infrastructure
#    4. Databases / Data Platforms
#    5. Data Processing / Orchestration
#    6. Analytics / Machine Learning
#    7. DevOps / CI-CD / Version Control
#    8. Business Intelligence / Visualization
#    9. Testing / Quality Assurance
#    10. Methodologies / Practices
#    11. Other or Domain-specific categories (last)

# Example input:
# {{
#   "Programming Languages": ["Python", "SQL"],
#   "Tools": ["AWS", "Airflow", "Docker", "TensorFlow"]
# }}

# Example output:
# {{
#   "Programming Languages": ["Python", "SQL"],
#   "Cloud Platforms": ["AWS"],
#   "Data Orchestration": ["Airflow"],
#   "ML Frameworks": ["TensorFlow"],
#   "DevOps / Containers": ["Docker"]
# }}

# Now reorganize the following skills JSON:

# {skills_json}
# """
