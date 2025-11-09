import google.generativeai as genai 
import os
from typing import Optional
import json


# Sample function to test and fix the prompts based on the output results it give for that prompt

def chat_completion(prompt: str, response_schema: Optional[dict] = None) -> str:

    api_key = "AIzaSyAD8fiUgyxG_YT0TmtlvgqX_EMI-ietQPo"
    genai.configure(api_key=api_key)
    model_name = "gemini-2.5-flash"

     # Configure generation with schema if provided
    generation_config = {
        "temperature": 0.7,
    }
    
    if response_schema:
        generation_config["response_mime_type"] = "application/json"
        generation_config["response_schema"] = response_schema

    gmodel = genai.GenerativeModel(model_name=model_name, generation_config=generation_config)
    response = gmodel.generate_content(prompt)

    print("\n\nFull Response:", response, "\n\n")

    # Primary text
    text = getattr(response, "text", None)
    if text:
        return text.strip()

    # Fallback extraction if needed
    candidates = getattr(response, "candidates", None)
    if candidates:
        parts = []
        for cand in candidates:
            content = getattr(cand, "content", None)
            if content and hasattr(content, "parts"):
                parts.extend([str(p) for p in content.parts])
        return "\n".join(parts).strip()

    return ""

# Example usage
if __name__ == "__main__":


    jd_hints = {
        "technical_keywords": ["Azure", "web application development", "data engineering", "Postgres SQL", "Azure Synapse", "Azure App Services", "UI", "data workflows", "front-end", "back-end", "data layers", "data control frameworks", "Synapse", "CI/CD", "unit testing", "version control", "monitoring", "scripting", "automation", "QA/UAT cycles", "accessibility/usability checks", "Web GUI", "downstream reports/dashboards", "Databricks", "Azure DevOps", "Python", "SQL", "PySpark", "cloud data lakes", "Git", "Delta Lake", "Postgres database platforms", "Web UI services"],
        "soft_skills_role_keywords": ["Full Stack Data Engineer", "engineer", "developer", "tester", "business analyst", "building", "maintaining", "troubleshoot", "enhance", "Analyze", "resolve", "perform", "implement", "Design", "Collaborate", "understand", "deliver", "Participate", "contribute", "estimate", "Apply", "Use", "simplify", "improve", "Support", "Own", "Document", "self-driven", "thrives", "Agile team setup", "comfortable wearing multiple hats", "Passionate", "scalable data systems", "collaborating", "business stakeholders", "technical stakeholders", "analytical", "problem-solving", "critical thinking", "communication", "interpersonal abilities", "actuarial"],
        "phrases": ["building and maintaining scalable web applications and data workflows that support actuarial and business stakeholders", "work across the stack—from front-end interfaces to back-end data pipelines—ensuring performance, reliability, and compliance", "Build and maintain scalable web applications and data pipelines using Postgres SQL , Azure Synapse , and Azure App Services", "Maintain, troubleshoot, and enhance existing UI and data workflows to ensure data quality, system reliability, and performant user experiences", "Analyze and resolve production issues across front-end, back-end, and data layers; perform root cause analysis and implement long-term fixes", "Design and implement robust data control frameworks to ensure integrity, security, and compliance across Synapse and integrated applications", "Collaborate with actuarial stakeholders to understand data requirements and deliver reliable solutions", "Participate in Agile ceremonies, contribute to backlog grooming, and estimate tasks with the team", "Apply software engineering best practices including CI/CD, unit testing, version control, and monitoring", "Use scripting and automation to simplify deployment and improve team efficiency", "Own deliverables from development through testing and deployment", "Experience with Azure Synapse , Databricks , Azure DevOps , Azure App Service , and Postgres SQL"]
    }

    technical_skills= {
      "Languages & Frameworks": ["Java", "Python", "Scala", "SQL", "JavaScript", "TypeScript", "Spring Boot", "Spring Security", "Hibernate", "JPA", "Node.js"],
      "Frontend": ["React.js", "Angular", "TypeScript", "HTML", "CSS", "JavaFX"],
      "Databases & Messaging": ["PostgreSQL", "Oracle", "MongoDB", "Redis", "Kafka", "Kafka Streams", "RabbitMQ", "JMS"],
      "Cloud & Infrastructure": ["AWS (EC2, EKS, S3, Lambda, IAM, VPC)", "Docker", "Kubernetes", "Linux"],
      "CI/CD & DevOps": ["Jenkins", "Git", "GitLab CI", "Maven", "SonarQube", "Terraform", "Blue-Green & Rolling Deployments"],
      "Monitoring & Observability": ["CloudWatch", "Prometheus", "Grafana", "ELK Stack", "Splunk", "AppDynamics"],
      "Testing & Security": ["JUnit", "Mockito", "Selenium", "OAuth2", "JWT", "RBAC", "TLS"],
      "Data & Analytics": ["ETL Pipelines", "Power BI", "SQL Tuning", "Data Lineage"]
    }
    
    GENERATE_TECHNICAL_SKILLS_FROM_JD = """
Expert technical skills organizer. Extract and categorize technical skills from JD keywords while preserving relevant skills from existing resume.

GOAL: Create ATS-optimized technical skills section by merging JD requirements with candidate's existing skills.

INPUTS:
1. JD Technical Keywords (PRIORITY SOURCE): {jd_technical_keywords}
2. Existing Resume Skills (REFERENCE): {existing_skills}

EXTRACTION RULES:

1. Inclusion Logic:
   - Include ALL technical keywords from JD (100% priority)
   - Keep existing skills that are relevant to JD domain
   - Add related tools if JD mentions the technology family (e.g., JD has "Azure" → include "Azure Synapse, Azure DevOps")
   - Exclude outdated or irrelevant technologies not in JD

3. Categorization Strategy:
   - Group by logical categories matching industry standards
   - Keep 5-8 categories maximum (don't over-fragment)
   - Put most important JD skills in first 3 categories
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

OUTPUT FORMAT: JSON matching existing resume structure. Each category should have 3-8 items.

{{
  "Languages & Frameworks": ["...", "..."],
  "Cloud & Infrastructure": ["...", "..."],
  "Databases & Data": ["...", "..."],
  "DevOps & CI/CD": ["...", "..."],
  "Testing & Security": ["...", "..."],
  ...
}}


Now generate the technical skills section:

JD Technical Keywords:
{jd_technical_keywords}

Existing Resume Skills:
{existing_skills}
"""

    prompt = GENERATE_TECHNICAL_SKILLS_FROM_JD.format(
        jd_technical_keywords=", ".join(jd_hints["technical_keywords"]),
        existing_skills=json.dumps(technical_skills, indent=2)
    )

    # Define response schema - flexible category names
    skills_schema = {
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["categories"]
    }

    result = chat_completion(prompt)
    result = json.loads(result)

    print("Technical Skills Result:\n", result)
