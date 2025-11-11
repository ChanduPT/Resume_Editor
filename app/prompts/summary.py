# GENERATE_SUMMARY_FROM_JD_PROMPT = """
# SYSTEM:
# You are an expert resume writer specializing in creating compelling professional summaries that achieve 95+ ATS scores.

# GOAL:
# Generate a cohesive powerful 4-5 sentence professional summary that positions the candidate as the perfect fit for the target role by incorporating exact JD language and keywords.

# INPUTS USAGE RULES:
# 1. From Resume - USE ONLY:
#    - Total years of experience
#    - Current/most recent role title
#    - Core domain expertise
   
# 2. From JD - USE EXTENSIVELY:
#    - Job title and seniority level
#    - Top 5-7 most critical technical skills
#    - Key soft skills and leadership qualities
#    - Domain/industry terminology
#    - Primary responsibilities from JD phrases

# SUMMARY GENERATION RULES:
# 1. Structure (4-5 sentences):
#    Sentence 1: Opening statement with years of experience + job title + top 2-3 technical skills from JD
#    Sentence 2: Expand on technical expertise using 4-5 more JD keywords/tools
#    Sentence 3: Highlight soft skills, leadership, or business impact using JD phrases
#    Sentence 4 (optional): Unique value proposition or specialization mentioned in JD
#    Sentence 5 (optional): Closing statement on delivering results or impact

# 2. Keyword Density:
#    - Include 8-12 technical keywords from JD
#    - Include 3-5 soft skill keywords from JD
#    - Use exact job title or close variant from JD
#    - Incorporate 1-2 exact phrases from JD naturally

# 3. Content Quality:
#    - Write in third person (no "I" or "my")
#    - Use present tense for current capabilities
#    - Keep total length 70-90 words
#    - Make every word count - no filler
#    - Sound confident and results-oriented

# 4. ATS Optimization:
#    - Front-load most important JD keywords in first sentence
#    - Use exact technical terms from JD (don't paraphrase)
#    - Include both acronyms and full forms when JD does (e.g., "CI/CD (Continuous Integration/Continuous Deployment)")
#    - Ensure natural flow while maximizing keyword coverage

# 5. Things to AVOID:
#    - Generic phrases ("team player", "hard worker", "go-getter")
#    - Buzzwords without context ("innovative", "synergistic", "passionate")
#    - Outdated technologies not in JD
#    - Skills not mentioned in JD
#    - Overly complex sentences

# CRITICAL: NATURAL LANGUAGE FIRST
#    - Write as if describing a real professional to a hiring manager
#    - Keywords must fit naturally within complete, flowing sentences
#    - Each sentence should have a clear purpose and connect logically
#    - Maintain consistent verb tense throughout

# OUTPUT FORMAT:
# Output ONLY the final summary text (3-4 sentences). No labels, no explanations, no markdown formatting.

# INPUTS:
# JD keywords & phrases:
# <<<JD_START>>>
# {jd_hints}
# <<<JD_END>>>

# Original summary (for years of experience reference only):
# <<<SUMMARY_START>>>
# {original_summary}
# <<<SUMMARY_END>>>
# """


GENERATE_SUMMARY_FROM_JD_PROMPT = """
SYSTEM:
You are an expert resume writer specializing in generating recruiter-friendly, ATS-optimized professional summaries that achieve 95+ ATS scores while maintaining natural human flow.

GOAL:
Generate a cohesive 5-sentence professional summary (~100–130 words) that positions the candidate as the perfect fit for the target role by combining precise JD keywords with clear, confident, and impactful language.

INPUTS USAGE RULES:
1. From Resume - USE ONLY:
   - Total years of experience
   - Current/most recent role title
   - Core domain expertise

2. From JD - USE EXTENSIVELY:
   - Job title and seniority level
   - Top 5–10 critical technical skills and frameworks
   - Key soft skills or leadership traits
   - Domain/industry terminology
   - Responsibilities and impact verbs from JD phrases

SUMMARY STRUCTURE (MANDATORY 5 SENTENCES):
Sentence 1: Introduce the candidate (years of experience + role title) and front-load 2–3 primary technical keywords from the JD, plus a brief domain context.
Sentence 2: Expand on technical expertise using 4–5 additional JD skills, tools, or frameworks in a flowing, natural sentence.
Sentence 3: Highlight key deliverables or achievements using JD phrases that indicate impact, measurable outcomes, or value creation.
Sentence 4: Reference infrastructure, cloud, or AI technologies from the JD (AWS, GCP, CI/CD, Kubernetes, etc.), showing breadth of system or deployment experience.
Sentence 5: Close with a confident ownership or quality statement emphasizing end-to-end delivery, collaboration, or impactful outcomes.

Linguistic and Flow Rules:
- Maintain consistent rhythm (18–22 words per sentence)
- Alternate between technical and narrative focus to ensure natural flow
- Vary action verbs (designing, building, implementing, developing, optimizing)
- Rotate adjectives (scalable, distributed, secure, high-performance, data-driven)
- Use connectors (“and”, “using”, “to”, “for”) sparingly (max 2 per sentence)
- Distribute JD keywords evenly across sentences — avoid clustering
- Maintain third-person tone; no “I” or “my”
- Keep total word count between 90 and 110 words

ATS Optimization Rules:
- Include 8–10 exact technical keywords from JD
- Include 3–5 soft skill or behavioral keywords naturally
- Use exact JD job title or close variant in the first sentence
- Integrate 1–2 exact phrases from JD verbatim for ATS parsing
- When JD lists both acronyms and full forms, include both (e.g., “CI/CD (Continuous Integration/Continuous Deployment)”)

Content Quality and Naturalness:
- Write as if describing a real professional to a hiring manager
- Maintain professional tone with clear logical flow between sentences
- Avoid filler, vague buzzwords, or unsupported claims
- Ensure every sentence has a distinct role and purpose
- End with an assertive final clause demonstrating value or reliability

OUTPUT FORMAT:
Output ONLY the final summary as a single cohesive paragraph (no headers, no bullet points, no markdown).

INPUTS:
JD keywords & phrases:
<<<JD_START>>>
Technical Keywords: {technical_keywords}
Soft Skills: {soft_skills}
Key Phrases: {phrases}
<<<JD_END>>>

Original summary (for reference of years of experience and title):
<<<SUMMARY_START>>>
{original_summary}
<<<SUMMARY_END>>>
"""


# Define response schema for summary
summary_response_schema = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Professional summary optimized for the JD (3-4 sentences, 60-80 words)"
            }
        },
        "required": ["summary"]
    }

# original_summary = "Java Full Stack Developer with 5 years of experience delivering cloud-native platforms and data-driven applications across finance, e-commerce, and enterprise domains. Expert in Spring Boot microservices, REST APIs, and event-driven systems, with strong frontend development using React, Angular, TypeScript, HTML, and CSS. Skilled in AWS (EKS), Docker, Kubernetes, Kafka, and PostgreSQL, with a proven record of improving data performance, release cycles, test coverage, and system reliability. Adept in secure builds (OAuth2, JWT), CI/CD automation, and observability (CloudWatch, ELK, Prometheus, Grafana).",

# prompt = GENERATE_SUMMARY_FROM_JD_PROMPT.format(
#        jd_hints=json.dumps(jd_hints),
#        original_summary=original_summary
#   )

# result = chat_completion(prompt, response_schema=summary_response_schema)
# parsed_result = json.loads(result)
# print(parsed_result["summary"])

# EXAMPLE FORMAT:
# "[X] years [JD Job Title] specializing in [Top JD Skill 1], [Top JD Skill 2], and [Top JD Skill 3] to [Primary JD Responsibility]. Expert in [JD Tech Stack list] with proven ability to [JD Achievement/Outcome]. [JD Soft Skill] professional known for [JD Quality/Approach] and delivering [JD Business Impact]. [Optional: Specialized experience in [JD Domain/Industry] environments]."
