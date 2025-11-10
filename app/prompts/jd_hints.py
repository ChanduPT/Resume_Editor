JD_HINTS_PROMPT = """

    You are an expert in analyzing job descriptions for any technical or analytical role.

    The goal is to extract two main types of information from the provided job description (JD), which can be used to optimize a resume for Applicant Tracking Systems (ATS):

    1. Important keywords and terms
    2. Key phrases and sentences that should be reflected in the resume to get high ATS scores.

    PART 1 - Technical Keywords/Terms to extract:
    - Programming languages, frameworks, libraries, APIs
    - Cloud, DevOps, and infrastructure tools
    - Databases, ETL tools, data warehouses, pipelines
    - BI, analytics, ML, and visualization tools
    - Version control, SDLC, CI/CD, testing, and deployment practices
    - Agile, Scrum, and collaboration tools
    - Business domains (finance, healthcare, e-commerce, etc.)
    - Certifications and compliance standards (AWS Certified, HIPAA, GDPR, PMP, etc.)

    Part 1.2 - Soft Skills and Role-Specific Keywords:
    ONLY extract meaningful soft skills and role keywords. Like:
    - Specific job titles (Full Stack Data Engineer, Senior Developer, Data Analyst, Technical Lead)
    - Meaningful soft skills with context (cross-functional collaboration, stakeholder management, mentoring junior developers, technical leadership)
    - Domain expertise (actuarial, financial modeling, healthcare analytics, e-commerce optimization)
    - Team structure keywords (Agile team setup, cross-functional teams, distributed teams)
    - Business impact skills (business stakeholder collaboration, requirements gathering, solution architecture)
    
    DO NOT extract:
    - Single generic verbs without context (Use, Support, Own, Document, improve, simplify etc)
    - Overly common action words (building, maintaining, working, helping etc)
    - Basic work activities (analyze, resolve, implement, design, deliver, participate, contribute, estimate, apply etc)
    - Personal traits without professional context (self-driven, passionate, comfortable, thrives etc)
    - Generic capabilities that are expected in any job
    
    PART 2 - Phrases to extract:
    Extract exact phrases from the job description that would be impactful to include in a resume and help achieve a high ATS score.
    Don't paraphrase or summarize - provide the exact text.
    Focus on phrases that highlight:
        - Exact responsibilities or requirements statements
        - Project or achievement descriptions
        - Specific domain expertise descriptions
        - Team collaboration and leadership descriptions
    Keep only top 10 phrases that are most relevant and of high value to include in a resume to get an ATS score of 95+.

    Instructions:
        - Return ONLY valid JSON matching the provided schema
        - Don't use any markdown formatting in the response.
        - Do not include any explanations or extra text - only provide the requested lists.
        - Don't paraphrase or summarize - provide the exact text where specified.
        - Don't hallucinate - only extract what is explicitly present in the JD.

    Here is the job description (JD):
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
            "soft_skills_role_keywords": {
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
        "required": ["technical_keywords", "soft_skills_role_keywords", "phrases"]
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

