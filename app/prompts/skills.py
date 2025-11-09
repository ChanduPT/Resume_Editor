GENERATE_TECHNICAL_SKILLS_FROM_JD = """
Expert technical skills organizer. Extract and categorize technical skills from JD keywords while preserving relevant skills from existing resume.

GOAL: Create ATS-optimized technical skills section by merging JD requirements with candidate's existing skills.

INPUTS:
1. JD Technical Keywords (PRIORITY SOURCE): {jd_technical_keywords}
2. Existing Resume Skills (REFERENCE): {existing_skills}

EXTRACTION RULES:

1. Inclusion Logic:
   - Include ALL technical keywords from JD (100% priority)
   - Exclude outdated or irrelevant technologies not in JD

3. Categorization Strategy:
   - Group by logical categories matching industry standards
   - Keep 5-8 categories maximum (don't over-fragment)
   - Order: Languages → Frameworks → Databases → Cloud → DevOps → Other

4. Use smart merging to avoid redundancy and ensure clarity.

5. Quality Rules:
   - No duplicates (PostgreSQL = Postgres SQL, choose one)
   - Use official names (PostgreSQL not "Postgres", Kubernetes not "K8s")
   - Group related items (Azure Synapse, Azure DevOps, Azure App Services → under Cloud)
   - Don't create categories with only 1-2 items (merge into "Other")

6. Things to AVOID:
   - Generic terms ("Databases", "Programming" without specifics)
   - Outdated tech not in JD (Flash, Silverlight, IE6)
   - Skills from existing resume that conflict with JD domain
   - Over-categorization (10+ categories)
   - Vague groupings ("Tools", "Technologies")

OUTPUT FORMAT: 
Return ONLY valid JSON. No markdown, no explanations, no additional text.
The JSON must follow this exact structure with dynamic category names:

{{
  "technical_skills": {{
    "category_name_1": ["skill1", "skill2", "skill3"],
    "category_name_2": ["skill1", "skill2"],
    "category_name_3": ["skill1", "skill2", "skill3", "skill4"]
  }}
}}


CRITICAL: Return ONLY the JSON object. Start with {{ and end with }}. No other text.

Now generate the technical skills section:

JD Technical Keywords:
{jd_technical_keywords}

Existing Resume Skills:
{existing_skills}
"""

# Skills response schema - set to None to get raw JSON output from prompt
# The model will generate JSON based on prompt instructions without schema validation
skills_response_schema = None

# prompt = GENERATE_TECHNICAL_SKILLS_FROM_JD.format(
#         jd_technical_keywords=", ".join(jd_hints["technical_keywords"]),
#         existing_skills=json.dumps(technical_skills, indent=2)
#     )


# result = chat_completion(prompt)
# result = json.loads(result)

# print("Technical Skills Result:\n", result)
