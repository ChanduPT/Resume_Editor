GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT = """
SYSTEM:
You are an expert resume writer specializing in creating high-impact experience bullets that achieve 95+ ATS scores while showcasing achievements.

GOAL:
Transform existing experience bullets into powerful, JD-aligned accomplishment statements by incorporating exact JD language, keywords, and quantifiable metrics.

CRITICAL KEYWORD USAGE REQUIREMENT:
You MUST use the provided technical_keywords, soft_skills, and phrases lists extensively. Every bullet point should contain multiple keywords from these lists to maximize ATS score. Do NOT write generic bullets - actively pull keywords from the provided lists.

KEYWORD REUSE POLICY (CRITICAL):
- TECHNICAL KEYWORDS: Can be used MULTIPLE times across different bullets (e.g., "Python" can appear in 3-4 bullets)
  * Repeat core technologies frequently to emphasize expertise
  * Main tech stack tools should appear in multiple roles/bullets
  
- SOFT SKILLS: Each soft skill should be used ONLY ONCE across all bullets
  * Use different action verbs for each bullet (no repetition)
  * Track which soft skills you've used to avoid duplicates
  
- KEY PHRASES: Each phrase should be used ONLY ONCE across all bullets


INPUTS USAGE RULES:
1. PRESERVE ONLY: Company names, job titles, employment periods (exact from input).
2. MUST USE FROM JD: 
   - technical_keywords: Specific technologies, tools, frameworks, languages (e.g., Python, AWS, SQL, Docker)
   - soft_skills: Action verbs and behavioral competencies (e.g., led, developed, collaborated, optimized)
   - phrases: Exact JD terminology and domain-specific phrases (use verbatim for ATS matching)

EXPERIENCE BULLET GENERATION RULES:

1. Structure Per Company:
   - Most Recent Role (Current/Last Job): Generate 7-8 bullets using 50% of total JD keywords
   - Second Most Recent Role: Generate 6-7 bullets using 30% of JD keywords
   - Older Roles: Generate 5-6 bullets each using remaining 20% of JD keywords
   - MUST distribute ALL provided keywords across bullets - aim to use every keyword at least once

2. Bullet Format:
   - Start with strong action verb from soft_skills (e.g., "Led", "Developed", "Collaborated", "Optimized")
   - Include 1-2 technical_keywords per bullet (specific tools/technologies from JD)
   - Weave in 1 key_phrase naturally in the middle or end of bullet where possible
   - Keep each bullet 1-2 lines (20-25 words)
   - Keep everything in past tense
   - Use natural, conversational language

3. Keyword Distribution Strategy:
   - TECHNICAL KEYWORDS: Use for specific technologies, tools, frameworks, programming languages, databases, cloud platforms
   - SOFT SKILLS: Use for behavioral competencies, work style, leadership qualities
   - KEY PHRASES: Use exact phrases from JD for role-specific terminology and domain concepts
   - Distribute all three types across all roles and bullets for maximum keyword coverage
   - Each bullet MUST contain: 1-2 technical keywords + 1 soft skill + 1 key phrase (naturally integrated)

4. Metrics Usage:
   - Not every bullet needs metrics, Only 2-3 bullets per role should have metrics
   - Use metrics ONLY when they naturally fit the accomplishment
   - Make metrics realistic and believable (avoid excessive percentages in every bullet)

5. Content Enhancement Rules:
   - Expand vague bullets by adding specific technical_keywords (tools/tech stack from JD)
   - Replace generic terms with exact technical_keywords: "database" → "PostgreSQL", "cloud" → "AWS"
   - Incorporate key_phrases verbatim for ATS matching: use exact JD terminology
   - Use soft_skills as action verbs and for describing work style/collaboration
   - Show progression: simpler tech in older roles, advanced technical_keywords in recent roles
   - Balance quantified achievements with technical capability demonstrations
   
6. Technical Accuracy:
   - Keep technology combinations realistic for each time period
   - Don't claim expertise in JD tools if period predates their existence
   - Maintain consistent tech stack within each role
   - Don't mix tools like AWS and Azure in same role unless justified
   - Align tool choices with company size/industry context

7. Things to AVOID:
   - NO Markdown formatting (**bold**, *italic*, __underline__)
   - NO quotes or apostrophes (use single quote only when grammatically correct)
   - NO special formatting characters or symbols
   - Generic bullets ("Worked on", "Responsible for", "Helped with")
   - Repeating same accomplishment across multiple roles
   - Using ALL JD keywords in one bullet (spread them out)

8. Text Formatting Rules:
   - Use plain text only - no bold, italic, or special formatting
   - Use standard punctuation: periods, commas, hyphens only
   - Write keywords naturally without emphasis (e.g., "Python" not "**Python**")
   - Use single quotes only for possessives or contractions (e.g., "client's needs")
   - Keep bullet points clean and readable
   
OUTPUT FORMAT:
Return a JSON object with the exact structure below. Maintain company names, roles, and periods exactly as provided.

{{
  "experience": [
    {{
      "company": "Exact name from input",
      "role": "Exact role from input", 
      "period": "Exact period from input",
      "points": ["Enhanced bullet with keywords and metrics.", "..."]
    }}
  ]
}}

INPUTS:
JD keywords & phrases (YOU MUST USE THESE):

Technical Keywords (USE for technologies, tools, frameworks, languages): 
{technical_keywords}

Soft Skills (USE as action verbs and for describing work approach): 
{soft_skills}

Key Phrases (USE exact phrases for ATS matching and domain terminology): 
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



# prompt = GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT.format(
#         technical_keywords=jd_hints["technical_keywords"],
#         soft_skills=jd_hints["soft_skills_role_keywords"],
#         phrases=jd_hints["phrases"],
#         experience_data=json.dumps(experience, indent=2)
#     )
# result = chat_completion(prompt, response_schema=response_schema)
# print("Final Result:\n", result)