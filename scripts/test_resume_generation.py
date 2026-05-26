"""
Enhanced Resume Generation Test Suite
======================================
Tests all resume generation modes across 6 diverse JD types and reports:
  - Keyword coverage rate
  - Section completeness
  - Bullet quality (length, specificity)
  - Token usage and cost per call
  - Timing per phase

Run:  python scripts/test_resume_generation.py [--mode complete_jd|resume_jd|both] [--jd all|swe|ds|pm|devops|mkt|fs]

Results are saved to  debug_files/test_report_<timestamp>.json
"""

import sys, os, asyncio, json, time, argparse, textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Sample resume profile (realistic mid-career data engineer) ─────────────────
SAMPLE_RESUME = {
    "name": "Alex Rivera",
    "contact": {
        "email": "alex.rivera@email.com",
        "phone": "+1 555-123-4567",
        "linkedin": "linkedin.com/in/alexrivera",
        "location": "Austin, TX"
    },
    "summary": (
        "Data engineer with 5 years of experience designing scalable pipelines and "
        "analytics platforms. Proficient in Python, SQL, Spark, and cloud technologies. "
        "Track record of reducing data latency and improving system reliability."
    ),
    "technical_skills": {
        "Languages": ["Python", "SQL", "Scala", "Bash"],
        "Data & BI": ["Spark", "dbt", "Airflow", "Tableau", "Power BI"],
        "Databases": ["PostgreSQL", "Snowflake", "BigQuery", "Redis"],
        "Cloud": ["AWS (S3, Glue, Lambda, Redshift)", "GCP", "Terraform"],
        "Tools": ["Docker", "Kubernetes", "Git", "Jenkins", "Kafka"]
    },
    "experience": [
        {
            "company": "DataFlow Inc.",
            "role": "Senior Data Engineer",
            "period": "Jan 2022 – Present",
            "points": [
                "Designed and maintained 50+ Airflow DAGs processing 2TB daily across AWS S3/Redshift",
                "Reduced pipeline failure rate by 40% by implementing automated alerting and retry logic",
                "Led migration from on-prem Hadoop to AWS Glue, cutting infrastructure cost by $180K/year",
                "Built real-time streaming pipeline using Kafka and Spark Structured Streaming",
            ]
        },
        {
            "company": "Analytics Corp",
            "role": "Data Engineer",
            "period": "Jun 2020 – Dec 2021",
            "points": [
                "Developed ETL pipelines in Python and dbt transforming 500M+ records monthly",
                "Optimized complex SQL queries reducing report generation time from 4h to 15min",
                "Collaborated with data science team to deploy ML feature stores on Snowflake",
            ]
        },
        {
            "company": "Startup XYZ",
            "role": "Junior Data Analyst",
            "period": "Jul 2019 – May 2020",
            "points": [
                "Built Tableau dashboards used by C-suite for weekly business reviews",
                "Wrote Python scripts to automate data validation and QA processes",
            ]
        }
    ],
    "education": [
        {"degree": "B.S. Computer Science", "institution": "University of Texas at Austin", "year": "2019"}
    ],
    "projects": [
        {
            "name": "Open Source dbt Audit Plugin",
            "bullets": [
                "Built a dbt package that auto-generates audit trails for all model runs",
                "Published on dbt Hub with 300+ downloads"
            ]
        }
    ],
    "certifications": [
        {"name": "AWS Certified Data Analytics", "organization": "Amazon Web Services", "year": "2022"},
        {"name": "Google Professional Data Engineer", "organization": "Google Cloud", "year": "2023"}
    ]
}

# ── JD test corpus ──────────────────────────────────────────────────────────────
JD_CORPUS: Dict[str, Dict[str, str]] = {

    "swe": {
        "label": "Software Engineer (Python/React)",
        "company": "TechStartup",
        "title": "Software Engineer",
        "jd": textwrap.dedent("""
            We are looking for a skilled Software Engineer to join our team.

            RESPONSIBILITIES:
            - Design, develop, and maintain scalable backend services in Python (FastAPI/Django)
            - Build responsive React frontends with TypeScript and modern state management
            - Write clean, testable code with >80% coverage (pytest, Jest)
            - Participate in code reviews and uphold engineering best practices
            - Work with PostgreSQL, Redis, and AWS infrastructure (EC2, RDS, S3)
            - Collaborate with cross-functional teams in an agile environment

            REQUIREMENTS:
            - 3+ years experience in backend Python development
            - Strong SQL skills and experience with relational databases
            - Proficiency with React and TypeScript
            - Experience with Docker, CI/CD pipelines (GitHub Actions or Jenkins)
            - Familiarity with REST API design and microservices architecture
            - Strong problem-solving and communication skills

            NICE TO HAVE:
            - Experience with Kafka or other message brokers
            - Knowledge of Kubernetes and Terraform
            - Open source contributions
        """).strip()
    },

    "ds": {
        "label": "Senior Data Scientist (ML/AI)",
        "company": "AI Labs",
        "title": "Senior Data Scientist",
        "jd": textwrap.dedent("""
            AI Labs is hiring a Senior Data Scientist to lead our machine learning efforts.

            WHAT YOU'LL DO:
            - Develop and deploy production ML models using Python (scikit-learn, XGBoost, PyTorch)
            - Design A/B experiments and analyze results with statistical rigor
            - Build feature engineering pipelines using Spark and Databricks
            - Collaborate with engineering to ship models to production via MLflow
            - Mentor junior data scientists and establish ML best practices
            - Communicate findings to executive stakeholders with clear data storytelling

            REQUIREMENTS:
            - 5+ years of industry data science experience
            - Strong Python skills: pandas, numpy, scikit-learn, PyTorch or TensorFlow
            - Deep expertise in statistics, probability, and experimental design
            - Experience with Spark, Databricks, or similar distributed compute
            - Proficiency with SQL and large-scale data processing
            - Experience with MLflow, Kubeflow, or similar MLOps platforms

            PREFERRED:
            - PhD in Statistics, CS, or related field
            - NLP or computer vision experience
            - Experience with LLMs and prompt engineering
        """).strip()
    },

    "pm": {
        "label": "Product Manager (non-technical)",
        "company": "SaaS Co",
        "title": "Senior Product Manager",
        "jd": textwrap.dedent("""
            We're looking for a Senior Product Manager to drive our core product roadmap.

            RESPONSIBILITIES:
            - Define and prioritize the product roadmap based on customer research and business strategy
            - Write detailed PRDs and user stories for engineering teams
            - Conduct user interviews, usability tests, and analyze product metrics
            - Work cross-functionally with Design, Engineering, Sales, and Customer Success
            - Own the product launch process from beta to GA
            - Track KPIs and OKRs; run data-driven retrospectives

            REQUIREMENTS:
            - 4+ years of product management experience in B2B SaaS
            - Strong analytical skills; comfortable with Mixpanel, Amplitude, or similar tools
            - Excellent written and verbal communication skills
            - Experience with agile methodologies (Scrum, Kanban)
            - Proven track record of shipping products that users love
            - Ability to influence without authority across the organization

            PREFERRED:
            - Technical background (CS degree or engineering experience) is a plus
            - Experience with enterprise software or data products
        """).strip()
    },

    "devops": {
        "label": "DevOps / Cloud Engineer",
        "company": "CloudNative Corp",
        "title": "Senior DevOps Engineer",
        "jd": textwrap.dedent("""
            CloudNative Corp is seeking a Senior DevOps Engineer to scale our infrastructure.

            RESPONSIBILITIES:
            - Design and manage Kubernetes clusters on AWS EKS and GKE
            - Build and maintain CI/CD pipelines with GitHub Actions, ArgoCD, and Helm
            - Implement infrastructure-as-code using Terraform and Ansible
            - Monitor system health with Datadog, Prometheus, and Grafana
            - Drive security hardening: IAM policies, secrets management (Vault), network policies
            - Lead incident response and root cause analysis for production outages

            REQUIREMENTS:
            - 4+ years DevOps/SRE/Platform Engineering experience
            - Expert-level Kubernetes and container orchestration (Docker, Helm)
            - Strong Terraform and cloud infrastructure experience (AWS preferred)
            - Proficiency with CI/CD tools and GitOps workflows
            - Linux administration and Bash scripting expertise
            - Experience with monitoring/observability stacks

            NICE TO HAVE:
            - Kafka or message queue management
            - Service mesh experience (Istio, Linkerd)
            - CKA or AWS certifications
        """).strip()
    },

    "mkt": {
        "label": "Marketing Manager (non-tech)",
        "company": "BrandCo",
        "title": "Digital Marketing Manager",
        "jd": textwrap.dedent("""
            BrandCo is looking for a Digital Marketing Manager to lead growth initiatives.

            RESPONSIBILITIES:
            - Develop and execute multi-channel digital marketing campaigns (SEO, SEM, email, social)
            - Manage $500K annual paid media budget across Google Ads, LinkedIn, and Meta
            - Build and optimize marketing automation workflows in HubSpot
            - Analyze campaign performance using Google Analytics 4 and Looker
            - Lead content strategy and oversee a team of 3 content creators
            - Report weekly on CAC, LTV, ROAS, and funnel metrics to leadership

            REQUIREMENTS:
            - 5+ years B2B digital marketing experience
            - Demonstrated expertise in paid media strategy and budget management
            - Proficiency with HubSpot, Salesforce, or similar CRM/MAP tools
            - Strong analytical mindset; fluent in GA4, attribution models, and A/B testing
            - Excellent written communication and presentation skills
            - Experience managing and mentoring a team

            PREFERRED:
            - Experience marketing analytics or data products
            - Account-based marketing (ABM) strategy experience
        """).strip()
    },

    "fs": {
        "label": "Full Stack Engineer (React/Node)",
        "company": "FinTech Startup",
        "title": "Full Stack Engineer",
        "jd": textwrap.dedent("""
            We are building the next generation of financial infrastructure and need a
            Full Stack Engineer to help us ship.

            WHAT YOU'LL BUILD:
            - React/TypeScript frontend with complex financial data visualizations (D3.js, Recharts)
            - Node.js/Express or Fastify backend APIs with real-time WebSocket support
            - PostgreSQL schema design, migrations, and query optimization
            - Integration with Stripe, Plaid, and other financial APIs
            - Secure authentication flows: OAuth 2.0, JWT, MFA

            REQUIREMENTS:
            - 4+ years full-stack development experience
            - Expert React and TypeScript skills
            - Solid Node.js backend experience (Express, Fastify, or NestJS)
            - PostgreSQL proficiency; bonus for Redis or time-series DBs
            - Familiarity with AWS (Lambda, SQS, RDS) or GCP
            - Experience with Docker and CI/CD best practices

            BONUS:
            - Prior fintech or payments domain experience
            - Experience with GraphQL or gRPC
            - Open source contributions
        """).strip()
    },
}

# ── Analysis helpers ────────────────────────────────────────────────────────────

def count_keywords_covered(jd_text: str, bullets: List[str]) -> Dict[str, Any]:
    """Simple keyword coverage: count JD tech terms found in generated bullets."""
    jd_lower = jd_text.lower()
    bullets_text = " ".join(bullets).lower()
    # Extract "important" words: capitalized or 4+ char tokens
    import re
    tokens = set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9+#.]{2,}\b', jd_text))
    jd_tokens = {t.lower() for t in tokens if t[0].isupper() or len(t) >= 4}
    covered = {t for t in jd_tokens if t in bullets_text}
    pct = round(100 * len(covered) / max(len(jd_tokens), 1), 1)
    return {"jd_keywords": len(jd_tokens), "covered": len(covered), "coverage_pct": pct}

def analyze_bullets(bullets: List[str]) -> Dict[str, Any]:
    """Quality metrics for a list of bullet strings."""
    if not bullets:
        return {"count": 0, "avg_words": 0, "min_words": 0, "max_words": 0,
                "has_metrics": 0, "quality_score": 0}
    import re
    word_counts = [len(b.split()) for b in bullets]
    has_metric  = [bool(re.search(r'\d+[%$KMB]?|\d+x|\d+\+', b)) for b in bullets]
    avg_words   = round(sum(word_counts) / len(word_counts), 1)
    quality     = round(min(100, avg_words * 3 + sum(has_metric) * 10), 1)
    return {
        "count":       len(bullets),
        "avg_words":   avg_words,
        "min_words":   min(word_counts),
        "max_words":   max(word_counts),
        "has_metrics": sum(has_metric),
        "quality_score": quality,
    }

def analyze_resume(resume_json: dict, jd_text: str) -> Dict[str, Any]:
    """Full analysis of a generated resume dict."""
    all_bullets = []
    exp_list = resume_json.get("experience", [])
    for exp in exp_list:
        all_bullets.extend(exp.get("points", exp.get("bullets", [])))

    proj_bullets = []
    for proj in resume_json.get("projects", []):
        proj_bullets.extend(proj.get("bullets", proj.get("points", [])))

    coverage  = count_keywords_covered(jd_text, all_bullets + proj_bullets)
    exp_stats = analyze_bullets(all_bullets)

    sections_present = {
        "summary":        bool(resume_json.get("summary", "").strip()),
        "experience":     len(exp_list) > 0,
        "skills":         bool(resume_json.get("technical_skills")),
        "education":      len(resume_json.get("education", [])) > 0,
        "projects":       len(resume_json.get("projects", [])) > 0,
        "certifications": len(resume_json.get("certifications", [])) > 0,
    }
    completeness = round(100 * sum(sections_present.values()) / len(sections_present), 1)

    return {
        "sections_present": sections_present,
        "completeness_pct": completeness,
        "num_experiences":  len(exp_list),
        "keyword_coverage": coverage,
        "bullet_stats":     exp_stats,
        "summary_words":    len(resume_json.get("summary", "").split()),
        "num_skill_categories": len(resume_json.get("technical_skills", {})),
    }


# ── Core test runner ────────────────────────────────────────────────────────────

async def run_single_test(
    jd_key: str,
    jd_info: dict,
    mode: str,
    test_id: str,
) -> Dict[str, Any]:
    """Run one full resume generation cycle and return a result dict."""
    from app.job_processing import extract_jd_keywords, generate_resume_content
    from app.database import SessionLocal, ResumeJob

    print(f"\n{'─'*70}")
    print(f"  TEST: {jd_info['label']}  |  mode={mode}  |  id={test_id}")
    print(f"{'─'*70}")

    db = SessionLocal()
    result = {
        "test_id":    test_id,
        "jd_type":    jd_key,
        "jd_label":   jd_info["label"],
        "mode":       mode,
        "company":    jd_info["company"],
        "job_title":  jd_info["title"],
        "phases":     {},
        "token_summary": {},
        "analysis":   {},
        "errors":     [],
    }

    try:
        # Persist a stub ResumeJob so progress updates don't fail
        job = ResumeJob(
            user_id="test_runner",
            request_id=test_id,
            company_name=jd_info["company"],
            job_title=jd_info["title"],
            mode=mode,
            jd_text=jd_info["jd"],
            resume_input_json=SAMPLE_RESUME,
            status="pending",
        )
        db.add(job); db.commit()

        payload = {
            "resume_data": SAMPLE_RESUME,
            "mode":        mode,
            "job_description_data": {
                "job_description": jd_info["jd"],
                "company_name":    jd_info["company"],
                "job_title":       jd_info["title"],
            }
        }

        # ── PHASE 1: Keyword extraction ────────────────────────────────────────
        print(f"  [1/2] Extracting keywords …", end=" ", flush=True)
        t0 = time.time()
        try:
            feedback_data = await extract_jd_keywords(payload, request_id=test_id, db=db)
            phase1_dur = round(time.time() - t0, 2)
            result["phases"]["keyword_extraction"] = {
                "status": "ok",
                "duration_s": phase1_dur,
                "keywords_found": len(feedback_data.get("technical_keywords", [])),
                "soft_skills_found": len(feedback_data.get("soft_skills", [])),
                "phrases_found": len(feedback_data.get("phrases", [])),
            }
            print(f"✓ {phase1_dur}s  ({result['phases']['keyword_extraction']['keywords_found']} keywords)")
        except Exception as e:
            phase1_dur = round(time.time() - t0, 2)
            result["phases"]["keyword_extraction"] = {"status": "error", "error": str(e), "duration_s": phase1_dur}
            result["errors"].append(f"Phase1: {e}")
            print(f"✗ {e}")
            return result

        # ── PHASE 2: Content generation ────────────────────────────────────────
        print(f"  [2/2] Generating resume content …", end=" ", flush=True)
        t1 = time.time()
        try:
            resume_json = await generate_resume_content(
                request_id=test_id, feedback=None, db=db, mode=mode
            )
            phase2_dur = round(time.time() - t1, 2)
            result["phases"]["content_generation"] = {"status": "ok", "duration_s": phase2_dur}
            print(f"✓ {phase2_dur}s")
        except Exception as e:
            phase2_dur = round(time.time() - t1, 2)
            result["phases"]["content_generation"] = {"status": "error", "error": str(e), "duration_s": phase2_dur}
            result["errors"].append(f"Phase2: {e}")
            print(f"✗ {e}")
            return result

        result["total_duration_s"] = round(phase1_dur + phase2_dur, 2)

        # ── Pull token stats from DB for this request ──────────────────────────
        from app.database import LLMCallLog
        logs = db.query(LLMCallLog).filter(LLMCallLog.request_id == test_id).all()
        token_summary = {
            "total_calls":    len(logs),
            "total_tokens":   sum(l.total_tokens for l in logs),
            "prompt_tokens":  sum(l.prompt_tokens for l in logs),
            "output_tokens":  sum(l.completion_tokens for l in logs),
            "total_cost_usd": round(sum(l.cost_usd for l in logs), 6),
            "by_call": [
                {
                    "call_name": l.call_name,
                    "prompt_tokens": l.prompt_tokens,
                    "output_tokens": l.completion_tokens,
                    "cost_usd": l.cost_usd,
                    "duration_s": l.duration_seconds,
                }
                for l in sorted(logs, key=lambda x: x.created_at)
            ]
        }
        result["token_summary"] = token_summary

        # ── Qualitative analysis ───────────────────────────────────────────────
        result["analysis"] = analyze_resume(resume_json, jd_info["jd"])
        result["generated_resume"] = resume_json   # store for inspection

    except Exception as e:
        result["errors"].append(f"Unexpected: {e}")
        print(f"  ✗ Unexpected error: {e}")
    finally:
        # Clean up test job from DB
        try:
            job = db.query(ResumeJob).filter(ResumeJob.request_id == test_id).first()
            if job:
                db.delete(job); db.commit()
        except Exception:
            pass
        db.close()

    return result


# ── Report printer ──────────────────────────────────────────────────────────────

def print_report(results: List[Dict[str, Any]]):
    col = {
        "label": 36, "mode": 12, "kw": 7, "cov": 7, "bullets": 7,
        "q": 7, "tokens": 9, "cost": 10, "time": 8, "ok": 5
    }
    sep = "─" * 115

    header = (
        f"{'JD Type':<{col['label']}} {'Mode':<{col['mode']}} "
        f"{'KW%':>{col['kw']}} {'Cov%':>{col['cov']}} "
        f"{'Bullets':>{col['bullets']}} {'Qual':>{col['q']}} "
        f"{'Tokens':>{col['tokens']}} {'Cost($)':>{col['cost']}} "
        f"{'Time(s)':>{col['time']}} {'OK':>{col['ok']}}"
    )
    print(f"\n{'═'*115}")
    print("  RESUME GENERATION TEST REPORT")
    print(f"{'═'*115}")
    print(f"  {header}")
    print(f"  {sep}")

    total_tokens = 0; total_cost = 0.0; n_ok = 0

    for r in results:
        ok = not r["errors"] and r["phases"].get("content_generation", {}).get("status") == "ok"
        n_ok += int(ok)
        an   = r.get("analysis", {})
        ts   = r.get("token_summary", {})
        bs   = an.get("bullet_stats", {})
        kw   = an.get("keyword_coverage", {})

        tokens = ts.get("total_tokens", 0)
        cost   = ts.get("total_cost_usd", 0.0)
        total_tokens += tokens; total_cost += cost

        cov_pct = kw.get("coverage_pct", "-")
        qual    = bs.get("quality_score", "-")
        bullets = bs.get("count", "-")
        dur     = r.get("total_duration_s", "-")

        row = (
            f"  {r['jd_label']:<{col['label']}} {r['mode']:<{col['mode']}} "
            f"{cov_pct:>{col['kw']}} {an.get('completeness_pct', '-'):>{col['cov']}} "
            f"{bullets:>{col['bullets']}} {qual:>{col['q']}} "
            f"{tokens:>{col['tokens']}} {cost:>{col['cost']}.6f} "
            f"{dur:>{col['time']}} {'✓' if ok else '✗':>{col['ok']}}"
        )
        print(row)
        if not ok:
            for e in r["errors"]:
                print(f"    ↳ ERROR: {e}")

    print(f"  {sep}")
    print(f"  {'TOTAL':} {n_ok}/{len(results)} passed  |  tokens={total_tokens:,}  |  cost=${total_cost:.6f}")
    print(f"{'═'*115}\n")


# ── Section-level breakdown ────────────────────────────────────────────────────

def print_section_breakdown(results: List[Dict[str, Any]]):
    print(f"\n{'─'*70}")
    print("  SECTION COMPLETENESS DETAIL")
    print(f"{'─'*70}")
    for r in results:
        an = r.get("analysis", {})
        sp = an.get("sections_present", {})
        missing = [s for s, v in sp.items() if not v]
        label = f"{r['jd_label'][:32]} ({r['mode']})"
        miss_str = ", ".join(missing) if missing else "none"
        print(f"  {label:<45}  missing: {miss_str}")


def print_token_breakdown(results: List[Dict[str, Any]]):
    print(f"\n{'─'*70}")
    print("  TOKEN COST PER CALL-TYPE  (aggregated across all tests)")
    print(f"{'─'*70}")
    agg: Dict[str, Dict] = {}
    for r in results:
        for call in r.get("token_summary", {}).get("by_call", []):
            k = call["call_name"] or "unknown"
            if k not in agg:
                agg[k] = {"calls": 0, "prompt": 0, "output": 0, "cost": 0.0}
            agg[k]["calls"]  += 1
            agg[k]["prompt"] += call["prompt_tokens"]
            agg[k]["output"] += call["output_tokens"]
            agg[k]["cost"]   += call["cost_usd"]

    for k in sorted(agg, key=lambda x: -agg[x]["cost"]):
        v = agg[k]
        print(f"  {k:<35} calls={v['calls']:>3}  "
              f"in={v['prompt']:>7,}  out={v['output']:>6,}  "
              f"cost=${v['cost']:.6f}")
    print()


# ── Main ────────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Resume generation test suite")
    parser.add_argument("--mode", default="both", choices=["complete_jd", "resume_jd", "both"])
    parser.add_argument("--jd",   default="all",  help="Comma-separated JD keys or 'all'")
    parser.add_argument("--save", action="store_true", help="Save JSON report to debug_files/")
    args = parser.parse_args()

    modes = ["complete_jd", "resume_jd"] if args.mode == "both" else [args.mode]

    if args.jd == "all":
        jd_keys = list(JD_CORPUS.keys())
    else:
        jd_keys = [k.strip() for k in args.jd.split(",") if k.strip() in JD_CORPUS]
        if not jd_keys:
            print(f"Unknown JD key(s). Available: {list(JD_CORPUS.keys())}"); return

    print(f"\n{'═'*70}")
    print(f"  Resume Generation Test Suite — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  JD types: {jd_keys}")
    print(f"  Modes:    {modes}")
    print(f"  Total tests: {len(jd_keys) * len(modes)}")
    print(f"{'═'*70}")

    results = []
    for jd_key in jd_keys:
        for mode in modes:
            ts = datetime.now().strftime("%H%M%S%f")[:10]
            test_id = f"test_{jd_key}_{mode[:4]}_{ts}"
            result = await run_single_test(jd_key, JD_CORPUS[jd_key], mode, test_id)
            results.append(result)

    print_report(results)
    print_section_breakdown(results)
    print_token_breakdown(results)

    if args.save or True:  # always save
        out_dir = Path("debug_files")
        out_dir.mkdir(exist_ok=True)
        fname = out_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        # Strip generated_resume for compactness (keep analysis only)
        slim = [{k: v for k, v in r.items() if k != "generated_resume"} for r in results]
        fname.write_text(json.dumps(slim, indent=2, default=str))
        print(f"  Report saved → {fname}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
