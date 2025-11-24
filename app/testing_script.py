# sample test to script to check the llm output for the given prompt
import asyncio
import json
from app.prompts.experience import GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT, experience_response_schema
from app.prompts.jd_hints import JD_HINTS_PROMPT, jd_hints_response_schema
from app.prompts.summary import GENERATE_SUMMARY_FROM_JD_PROMPT, summary_response_schema

from app.utils import chat_completion_async

async def test_jd_hints_prompt(sample_jd=None):
    jd_hints_raw = await chat_completion_async(
            JD_HINTS_PROMPT.format(jd_text=sample_jd),
            response_schema=jd_hints_response_schema,
            timeout=90  # 90 seconds timeout for JD analysis
        )
    
    jd_hints = json.loads(jd_hints_raw)
    
    # print the extracted hints
    print("Extracted JD Hints:")
    # print Keywords, Skills, and Phrases
    print("Keywords:")
    print(f"- {jd_hints['technical_keywords']}")
    print("Skills:")
    print(f"- {jd_hints['soft_skills']}")
    print("Phrases:")
    print(f"- {jd_hints['phrases']}")


# test experience
# Extract only company, role, period (no bullets) for complete_jd mode
async def test_experience_extraction(jd_hints=None, experience_metadata=None, role_title=None, role_seniority=None, role_requirements=None):

    prompt = GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT.format(
                    technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
                    soft_skills=json.dumps(jd_hints.get("soft_skills", []), ensure_ascii=False),
                    phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
                    experience_data=json.dumps(experience_metadata, ensure_ascii=False, indent=2),
                    role_title=role_title,
                    role_seniority=role_seniority,
                    jd_requirements=json.dumps(list(role_requirements), ensure_ascii=False, indent=2)
                )
    llm_response = await chat_completion_async(
        prompt,
        response_schema=experience_response_schema,
        timeout=90  # 90 seconds timeout for experience extraction
    )
    print("Extracted Experience Bullets:")
    print(llm_response)
    print("\n")
    # no of points in each experience
    experiences = json.loads(llm_response)
    for exp in experiences:
        company = exp.get("company", "Unknown Company")
        role = exp.get("role", "Unknown Role")
        bullets = exp.get("points", [])
        print(f"Experience at {company} as {role} has {len(bullets)} bullet points.")


# summary test
async def test_summary_extraction(jd_hints=None, original_summary=None):
    
    prompt = GENERATE_SUMMARY_FROM_JD_PROMPT.format(
           technical_keywords=json.dumps(jd_hints.get("technical_keywords", []), ensure_ascii=False),
           soft_skills=json.dumps(jd_hints.get("soft_skills", []), ensure_ascii=False),
           phrases=json.dumps(jd_hints.get("phrases", []), ensure_ascii=False),
           original_summary=original_summary
      )

    result = await chat_completion_async(
        prompt,
        response_schema=summary_response_schema,
        timeout=90  # 90 seconds timeout for summary generation
    )
    print("Generated Summary:")
    print(result)



if __name__ == "__main__":

    # Run tests
    sample_jd = """
    [RESPONSIBILITIES]
    Facilitate data-informed decision-making across the organization\n
    Partner with leaders at all levels to understand important business problems, then own the full lifecycle of data-driven solutions: 
    analysis, metric definitions, transformation pipelines in dbt, experimentation, measurement, and data story-telling\n
    Collaborate with Product, Research, Customer Success, and Rev Ops to provide data products allow them to better measure the impact of their work and find new opportunities\n
    Work with data engineers on our team to help build our new Lake House in Databricks and document vital context about our data that can be used by both stakeholders and AI tools\n
    Increase your impact by continuously learning and evolving your workflows as AI technology matures.\n
    Form opinions that help Jellyfish support its customers in their AI journeys.\n
    Enable your stakeholders to have a bigger impact through the use of AI in their own analytics workflows.\n
    As necessary, build the data tools they need, be their expert-in-the-loop, or influence them to adopt new workflows.\n
    Be a leader in data best practices across the Research team and Jellyfish; mentor other team members to help in their growth\n\n
[REQUIREMENTS]\nStrong knowledge of SQL (preferably Databricks, Snowflake, or Redshift)\n
    Experience with data quality best practices and building data models in dbt\n
    Experience using Python (numpy, pandas, sklearn, etc.) across exploratory data analysis or predictive modeling\n
    Proven leadership and a track record of shipping improvements with product or GTM teams\n
    Proven ability to influence senior decision-makers with data-driven insights\n
    Strong perspective on using the appropriate data solution for the business need at hand\n
    Strong perspective on scaling analytics solutions across a company for both technical and non-technical users\n
    Ability to thrive in a fast-paced, constantly improving, start-up environment that focuses on solving problems with iterative technical solutions\n
    Growth mindset and flexibility to adapt to changing technology and workflows\n\n
[PREFERRED]\n
    B2B SaaS\n
    Start-up environments\n
    User interaction data and product usage analytics """

    """
    Keywords:
- ['SQL', 'Databricks', 'Snowflake', 'Redshift', 'dbt', 'Python', 'numpy', 'pandas', 'sklearn', 'Lake House', 'AI']
Skills:
- ['Facilitate', 'Partner', 'Own', 'Collaborate', 'Enable', 'Influence', 'Mentor', 'Shipping', 'Thrive', 'Adapt']
Phrases:
- ['Facilitate data-informed decision-making across the organization', 'own the full lifecycle of data-driven solutions', 'transformation pipelines in dbt', 'data story-telling', 'Collaborate with Product, Research, Customer Success, and Rev Ops', 'build our new Lake House in Databricks', 'document vital context about our data', 'Enable your stakeholders to have a bigger impact through the use of AI', 'influence senior decision-makers with data-driven insights', 'building data models in dbt', 'using Python across exploratory data analysis or predictive modeling', 'shipping improvements with product or GTM teams', 'scaling analytics solutions across a company', 'User interaction data and product usage analytics']   
            """
    jd_hints = {
        "technical_keywords": [
            "SQL", "Databricks", "Snowflake", "Redshift", "dbt", "Python", 
            "numpy", "pandas", "sklearn", "Data Lake", "AI"
        ],
        "soft_skills": [
            "Facilitate", "Partner", "Own", "Collaborate", "Enable", 
            "Influence", "Mentor", "Shipping", "Thrive", "Adapt"
        ],
        "phrases": [
            "Facilitate data-informed decision-making across the organization",
            "own the full lifecycle of data-driven solutions",
            "transformation pipelines in dbt",
            "data story-telling",
            "Collaborate with Product, Research, Customer Success",
            "build Data Lake House in Databricks",
            "document vital context about data",
            "Enable stakeholders to have a bigger impact through the use of AI",
            "influence senior decision-makers with data-driven insights",
            "building data models in dbt",
            "using Python across exploratory data analysis or predictive modeling",
            "scaling analytics solutions across a company",
            "User interaction data and product usage analytics"
        ]
    }

    experience_metadata = [
        {"company": "Walmart", "role": "Data Analyst", "period": "Jan 2020 - Dec 2022"},
        {"company": "Tesla", "role": "Business Analyst", "period": "Feb 2023 - Present"},
        {"company": "Optum ", "role": "Data Analyst", "period": "Mar 2019 - Dec 2019"},
        {"company": "Deloitte", "role": "Data Consultant", "period": "Jan 2018 - Feb 2019"},
    ]

    original_summary = """Data Analyst with 3+ years of experience in SQL, Python, and data visualization. Skilled in building data models, conducting exploratory data analysis, and delivering insights to drive business decisions. Proven ability to collaborate with cross-functional teams and influence stakeholders with data-driven recommendations. Experienced in fast-paced startup environments and passionate about leveraging AI to enhance analytics workflows."""  

    role_title = "Data Analyst"
    role_seniority = "staff-level"
    role_requirements = {
        "Strong knowledge of SQL (preferably Databricks, Snowflake, or Redshift)",
        "Experience with data quality best practices and building data models in dbt",
        "Experience using Python (numpy, pandas, sklearn, etc.) across exploratory data analysis or predictive modeling",
        "Proven leadership and a track record of shipping improvements with product or GTM teams",
        "Proven ability to influence senior decision-makers with data-driven insights",
        "Strong perspective on using the appropriate data solution for the business need at hand",
        "Strong perspective on scaling analytics solutions across a company for both technical and non-technical users",
        "Ability to thrive in a fast-paced, constantly improving, start-up environment that focuses on solving problems with iterative technical solutions",
        "Growth mindset and flexibility to adapt to changing technology and workflows"
    }

    
    #asyncio.run(test_jd_hints_prompt(sample_jd))
    asyncio.run(test_experience_extraction(jd_hints, experience_metadata, role_title, role_seniority, role_requirements))
    #asyncio.run(test_summary_extraction(jd_hints, original_summary))