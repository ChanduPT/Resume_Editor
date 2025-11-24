# JD_HINTS_PROMPT = """

#     You are an expert in analyzing job descriptions for any technical or analytical role.

#     The goal is to extract two main types of information from the provided job description (JD), which can be used to optimize a resume for Applicant Tracking Systems (ATS):

#     1. Important keywords and terms
#     2. Key phrases and sentences that should be reflected in the resume to get high ATS scores.

#     PART 1 - Technical Keywords/Terms to extract:
#     - Programming languages, frameworks, libraries, APIs
#     - Cloud, DevOps, and infrastructure tools
#     - Databases, ETL tools, data warehouses, pipelines
#     - BI, analytics, ML, and visualization tools
#     - Version control, SDLC, CI/CD, testing, and deployment practices
#     - Agile, Scrum, and collaboration tools
#     - Business domains (finance, healthcare, e-commerce, etc.)
#     - Certifications and compliance standards (AWS Certified, HIPAA, GDPR, PMP, etc.)

#     Part 1.2 - Soft Skills and Role-Specific Keywords:
#     ONLY extract meaningful soft skills and role keywords. Like:
#     - Specific job titles (Full Stack Data Engineer, Senior Developer, Data Analyst, Technical Lead)
#     - Meaningful soft skills with context (cross-functional collaboration, stakeholder management, mentoring junior developers, technical leadership)
#     - Domain expertise (actuarial, financial modeling, healthcare analytics, e-commerce optimization)
#     - Team structure keywords (Agile team setup, cross-functional teams, distributed teams)
#     - Business impact skills (business stakeholder collaboration, requirements gathering, solution architecture)
    
#     DO NOT extract:
#     - Single generic verbs without context (Use, Support, Own, Document, improve, simplify etc)
#     - Overly common action words (building, maintaining, working, helping etc)
#     - Basic work activities (analyze, resolve, implement, design, deliver, participate, contribute, estimate, apply etc)
#     - Personal traits without professional context (self-driven, passionate, comfortable, thrives etc)
#     - Generic capabilities that are expected in any job
    
#     PART 2 - Phrases to extract:
#     Extract exact phrases from the job description that would be impactful to include in a resume and help achieve a high ATS score.
#     Don't paraphrase or summarize - provide the exact text.
#     Focus on phrases that highlight:
#         - Exact responsibilities or requirements statements
#         - Project or achievement descriptions
#         - Specific domain expertise descriptions
#         - Team collaboration and leadership descriptions
#     Keep only top 10 phrases that are most relevant and of high value to include in a resume to get an ATS score of 95+.

#     Instructions:
#         - Return ONLY valid JSON matching the provided schema
#         - Don't use any markdown formatting in the response.
#         - Do not include any explanations or extra text - only provide the requested lists.
#         - Don't paraphrase or summarize - provide the exact text where specified.
#         - Don't hallucinate - only extract what is explicitly present in the JD.

#     Here is the job description (JD):
#     {jd_text}
#     """

# JD_HINTS_PROMPT = """
# You are an expert in analyzing job descriptions (JDs) for technical and analytical roles.
# Your task is to extract ONLY the most relevant keywords, skills, and phrases that will improve an Applicant Tracking System (ATS) score when tailoring a resume.

# -------------------------------------------------------
# INPUT CONTEXT
# -------------------------------------------------------
# The JD provided below has been PREPROCESSED and STRUCTURED.
# It contains:
# - Cleaned, normalized text (no fluff or boilerplate)
# - Metadata (Job Title, Seniority, Domain, Location)
# - Segmented sections: [RESPONSIBILITIES], [REQUIREMENTS], [PREFERRED]
# - Section weighting (Responsibilities = highest priority, then Requirements, then Preferred)

# Use this structure to prioritize keyword extraction:
# 1. Focus heavily on the [RESPONSIBILITIES] section for technical keywords.
# 2. Use [REQUIREMENTS] for confirming skills and tools.
# 3. Reference [PREFERRED] only for secondary or supporting skills.

# -------------------------------------------------------
# GOAL
# -------------------------------------------------------
# From the provided preprocessed JD, extract and validate three structured categories:
# 1. Technical Keywords (hard skills, tools, frameworks)
# 2. Soft Skills (behavioral or action-oriented verbs)
# 3. Key Phrases (domain-specific, multi-word phrases)

# -------------------------------------------------------
# VALIDATION LOGIC & RULES
# -------------------------------------------------------

# PART 1 – TECHNICAL KEYWORDS
# Extract up to 15 unique technical or domain-specific tools and technologies such as:
# - Programming languages, frameworks, APIs
# - Cloud, DevOps, and infrastructure tools (AWS, Azure, Docker, Kubernetes)
# - Databases, data warehouses, ETL, pipelines, orchestration tools
# - BI, analytics, visualization, ML/AI frameworks
# - SDLC, testing, CI/CD, version control tools
# - Domain tech (CRM, ERP, Salesforce, SAP, Snowflake, etc.)

# Validation Criteria:
# - Include only if explicitly mentioned in the JD.
# - Prefer terms from [RESPONSIBILITIES] > [REQUIREMENTS] > [PREFERRED].
# - Must appear near an action verb or competency phrase (e.g., “experience with”, “hands-on using”).
# - Prefer modern/relevant stacks over outdated ones.
# - Deduplicate synonyms (“AWS Cloud” → “AWS”).
# - Return as a clean list of capitalized skill names.

# PART 2 – SOFT SKILLS / ACTION VERBS
# Extract up to 7 strong soft skills or action verbs that reflect behavior, ownership, or leadership qualities.
# Examples: Led, Collaborated, Optimized, Designed, Implemented, Mentored, Analyzed.

# Validation Criteria:
# - Must appear in context (e.g., “collaborate with teams”, “led initiatives”).
# - Exclude generic verbs without measurable impact (“worked on”, “helped with”, “supported”).
# - Exclude adjectives or personality traits (“passionate”, “self-motivated”).
# - Use unique verbs only; no duplicates across list.
# - Preserve the verb’s original tense and form as in JD.

# PART 3 – KEY PHRASES
# Extract the top 10 multi-word phrases or short clauses (exact text, no paraphrasing) that increase ATS match likelihood.
# Examples:
# - “design and implement scalable data pipelines”
# - “develop and deploy RESTful APIs”
# - “work in cross-functional agile teams”

# Validation Criteria:
# - Must be 3–6 words long.
# - Must contain at least one noun and one verb.
# - Must represent a distinct responsibility, domain concept, or measurable outcome.
# - Must appear exactly in the JD (no paraphrasing or hallucination).
# - Remove duplicates or slight rewordings.

# -------------------------------------------------------
# GENERAL RULES
# -------------------------------------------------------
# - Always prefer terms appearing in the [RESPONSIBILITIES] section first.
# - Preserve capitalization for technologies, acronyms, and frameworks.
# - Maintain concise wording (phrases ≤ 15 words).
# - Prioritize high-frequency and domain-relevant terms.
# - Ensure balanced ratio: ~60% technical, ~25% soft, ~15% phrases.
# - Return only validated, unique, contextually grounded items.

# -------------------------------------------------------
# OUTPUT FORMAT (STRICT JSON)
# -------------------------------------------------------
# Return ONLY valid JSON with three fields:
# {{
#   "technical_keywords": ["keyword1", "keyword2", ...],
#   "soft_skills": ["skill1", "skill2", ...],
#   "phrases": ["exact phrase 1", "exact phrase 2", ...]
# }}

# Do NOT include markdown, commentary, or extra text.

# -------------------------------------------------------
# PREPROCESSED JOB DESCRIPTION (JD):
# {jd_text}
# """



JD_HINTS_PROMPT = """
You are an expert in analyzing job descriptions (JDs) to extract key information for resume optimization.
Your task is to extract keywords, skills, and phrases that will improve an Applicant Tracking System (ATS) score when tailoring a resume.

INPUT CONTEXT
The Job Description contains segmented sections [RESPONSIBILITIES], [REQUIREMENTS], [PREFERRED]

GOAL
From the provided Job Description, extract and validate three structured categories:
1. Technical Keywords (technical skills, tools, frameworks, etc.)
2. Soft Skills (behavioral or action-oriented verbs)
3. Key Phrases (domain-specific, multi-word phrases, etc.)


VALIDATION LOGIC & RULES

PART 1 – TECHNICAL KEYWORDS
Go through the JD([RESPONSIBILITIES], [REQUIREMENTS], [PREFERRED]) and Extract unique technical or domain-specific tools and technologies such as:
- Programming languages, frameworks, technologies 
- Cloud, DevOps, and infrastructure tools (AWS, Azure, Docker, Kubernetes)
- Databases, data warehouses, ETL, pipelines, orchestration tools
- BI, analytics, visualization, ML/AI frameworks
- SDLC, testing, CI/CD, version control tools
- front-end, back-end, full-stack frameworks
- Domain tech (CRM, ERP, Salesforce, SAP, Snowflake, etc.)

Validation Criteria:
- Include only if explicitly mentioned in the Job Description.
- Prefer modern/relevant stacks over outdated ones.
- Deduplicate synonyms (“AWS Cloud” → “AWS”).

PART 2 – SOFT SKILLS / ACTION VERBS
Extract up to 7-10 strong soft skills or action verbs that reflect behavior, ownership, or leadership qualities.
Examples: Led, Collaborated, Optimized, Designed, Implemented, Mentored, Analyzed etc.

Validation Criteria:
- Must appear in context (e.g., “collaborate with teams”, “led initiatives”).   
- Exclude generic verbs without measurable impact (“worked on”, “helped with”, “supported”).
- Exclude adjectives or personality traits (“passionate”, “self-motivated”).
- Use unique verbs only; no duplicates across list.
- Preserve the verb’s original tense and form as in JD.

PART 3 – KEY PHRASES
Extract the top 10-12 multi-word phrases or clauses from responsibilities and requirements (exact text, no paraphrasing) that must reflect in a resume to increase ATS match likelihood.
Examples:
- “design and implement scalable data pipelines”
- “develop and deploy RESTful APIs”

Validation Criteria:
- Must be transferable across companies.
- **REMOVE possessive pronouns**: "our", "their", "your" → make generic
- **REMOVE company-specific terms**: company names, internal team names, proprietary tech
- **ADD CONTEXT to vague verbs**
- **Length**: 3-8 words (concise but meaningful)
- Dont include company-specific terms, team names, or proprietary technologies.
- Must contain at least one noun and one verb.
- Must represent a distinct responsibility, domain concept, or measurable outcome.
- Must appear exactly in the JD (no paraphrasing or hallucination).
- Remove duplicates or slight rewordings.

GENERAL RULES
- Prioritize high-frequency and domain-relevant terms.
- Return only validated, unique, contextually grounded items.

OUTPUT FORMAT (STRICT JSON)
- Return the output in the exact provided JSON structure.
- Do NOT include markdown, commentary, or extra text.

JOB DESCRIPTION (JD):
{jd_text}
"""


# Properly formatted JSON schema for Gemini
jd_hints_response_schema = {
        "type": "object",
        "properties": {
            "technical_keywords": {
                "type": "array",
                "description": "List of technical keywords/terms extracted from the JD",
                "items": {
                    "type": "string"
                }
            },
            "soft_skills": {
                "type": "array",
                "description": "List of soft skills and role-specific keywords extracted from the JD",
                "items": {
                    "type": "string"
                }
            },
            "phrases": {
                "type": "array",
                "description": "List of exact, relevant phrases from the JD that could be adapted into resume bullets",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["technical_keywords", "soft_skills", "phrases"]
    }

sample_jd = """
    Job Title: Full Stack Data Engineer – Azure & Web Applications Location: Richmond, VA - preference is hybrid but open to fully remote for the right candidate
    Position Overview We are seeking a Full Stack Data Engineer with strong experience in Azure cloud technologies, web application development, and data engineering. 
    This role will focus on building and maintaining scalable web applications and data workflows that support actuarial and business stakeholders. 
    You’ll work across the stack—from front-end interfaces to back-end data pipelines—ensuring performance, reliability, and compliance. 
    Key Responsibilities Build and maintain scalable web applications and data pipelines using Postgres SQL , Azure Synapse , and Azure App Services Maintain, 
    troubleshoot, and enhance existing UI and data workflows to ensure data quality, system reliability, and performant user experiences Analyze and resolve production issues across front-end, back-end, and data layers; 
    perform root cause analysis and implement long-term fixes Design and implement robust data control frameworks to ensure integrity, security, 
    and compliance across Synapse and integrated applications Collaborate with actuarial stakeholders to understand data requirements and deliver 
    reliable solutions Participate in Agile ceremonies, contribute to backlog grooming, and estimate tasks with the team Apply software engineering best practices 
    including CI/CD, unit testing, version control, and monitoring Use scripting and automation to simplify deployment and improve team efficiency Support QA/UAT cycles, 
    including accessibility/usability checks for Web GUI and validation of downstream reports/dashboards Own deliverables from development through testing and deployment Document
      requirements, logic, and enhancement details for knowledge sharing and support Preferred Skills & Technologies Experience with Azure Synapse , Databricks , 
      Azure DevOps , Azure App Service , and Postgres SQL Strong coding skills in Python , SQL , and PySpark Experience working with cloud data lakes Familiarity 
      with building CI/CD pipelines and using Git for version control Who You Are A self-driven engineer who thrives in an Agile team setup Comfortable wearing multiple hats: 
        developer, tester, business analyst Passionate about building maintainable, scalable data systems Enjoy collaborating with both business and technical stakeholders 
        Qualifications Bachelor’s degree in Computer Science, Information Systems, Data Science, Mathematics, or a related field (non-technical degrees considered with strong 
        technical experience) Experience with Synapse/Delta Lake and Postgres database platforms Expertise in SQL , Python , and solid understanding of Azure App Service and 
        Web UI services Strong analytical, problem-solving, and critical thinking skills Excellent communication and interpersonal abilities Diversity creates a healthier atmosphere
    """

# prompt = JD_HINTS_PROMPT.format(jd_text=sample_jd)
# result = chat_completion(prompt, response_schema=jd_hints_response_schema)
# print(result)

