GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT = """
SYSTEM:
You are an expert resume writer specializing in creating high-impact experience bullets that achieve 95+ ATS scores while showcasing achievements.

GOAL:
Transform existing experience bullets into powerful, JD-aligned accomplishment statements by incorporating exact JD language, keywords, and quantifiable metrics.

INPUTS USAGE RULES:
1. PRESERVE ONLY: Company names, job titles, employment periods (exact from input).
2. USE FROM JD: Technical keywords, exact tool names, action verbs, domain terminology, metrics, workflows.

EXPERIENCE BULLET GENERATION RULES:

1. Structure Per Company:
   - Most Recent Role (Current/Last Job): Generate 7-8 bullets (50% of total JD keywords)
   - Second Most Recent Role: Generate 6-7 bullets (30% of JD keywords)
   - Older Roles: Generate 5-6 bullets each (20% of JD keywords distributed)

2. Bullet Format:
   - Start with strong action verb from JD keywords
   - Include 2-4 technical keywords from JD per bullet
   - Keep each bullet 1-2 lines (20-25 words)
   - Keep everything in past tense
   - Use natural, conversational language

3. Keyword Distribution Strategy:
   - Distribute keywords (technical_keywords, soft_skills, phrases) across all roles (no repetition)
   - Each bullet must contain at least 2-3 JD keywords naturally integrated

4. Metrics Usage:
   - Not every bullet needs metrics, Only 2-3 bullets per role should have metrics
   - Use metrics ONLY when they naturally fit the accomplishment
   - Make metrics realistic and believable (avoid excessive percentages in every bullet)

5. Content Enhancement Rules:
   - Expand vague bullets with JD-specific technical details
   - Include exact tool/technology names from JD
   - Use JD phrases verbatim when contextually appropriate
   - Show progression: simpler tasks in older roles, complex in recent
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
   - Outdated technologies not in JD
   - Passive voice ("Was responsible for" → "Led")
   - Excessive metrics - Don't force percentages into every bullet

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
JD keywords & phrases:
Technical Keywords: {technical_keywords}
Soft Skills: {soft_skills}
Key Phrases: {phrases}

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