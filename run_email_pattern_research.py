#!/usr/bin/env python3
"""
Run deep research on a Colombian company to discover its email pattern.
Output: reasoning + research + report + JSON (for ord_email_patterns).

Usage:
  python run_email_pattern_research.py "Ecopetrol"
  python run_email_pattern_research.py "Bancolombia" --domain bancolombia.com.co
  python run_email_pattern_research.py "Grupo Aval" --max-iterations 5 --max-time 15

Requires .env with OPENROUTER_API_KEY, BRIGHTDATA_API_KEY, and BRIGHTDATA_UNLOCKER_ZONE.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from pymongo import MongoClient


# Add project root to path
_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
# Load .env from script directory so OPENROUTER_API_KEY is found
load_dotenv(_project_root / ".env")

from deep_researcher import IterativeResearcher
from deep_researcher.llm_config import REASONING_MODEL, create_default_config


# Output instructions for the Email Pattern research agent
OUTPUT_INSTRUCTIONS = """
Your final response MUST end with a valid JSON block. Use this exact structure:

```json
{
  "company_research": {
    "common_name": "<common or public name of the company>",
    "industries": ["<industry 1>"],
    "sub_industries": ["<sub industry 1>"],
    "activities_by_industry": {
      "<sub industry 1>": ["<activity 1>", "<activity 2>"]
    },
    "additional_details": "<any other relevant company information found>"
  },
  "employees": [
    {
      "name": "<employee name>",
      "position": "<job title>",
      "details": "<any other linkedin/web details>"
    }
  ],
  "metadata": {
    "empresa": "<exact company name from input>",
    "nombre_fantasia": "<common/public name if different>",
    "dominio": "<company email domain from real addresses, or unknown.co if none>",
    "pais": "Colombia",
    "total_emails_encontrados": <total number of real emails found>
  },
  "formula_dominante": "<primary pattern e.g. first.last, or No detectada if none>",
  "detalles": [
    {
      "patron": "<pattern string>",
      "confianza": <0-100 numerical value>,
      "es_recomendado": true,
      "frecuencia": <number of real emails matching>
    }
  ],
  "ejemplo_emails": [
    {"email": "<real@domain.co>"}
  ],
  "ord_email_patterns": {
    "formula": [["<patron1>", <confianza value>, <true|false>]],
    "primary_pattern": "<patron with highest confidence>",
    "primary_confidence": <0-100 numerical value>
  },
  "email_validation": {
    "emails_tested": ["<email1>", "<email2>"],
    "delivery_status": {"<email1>": "delivered", "<email2>": "not_found"},
    "summary": "<full validation report from findings - e.g. DELIVERED: a@x.co. NOT FOUND: b@x.co>"
  }
}
```

- email_validation: Include when "Email Validation Results" are in the findings. Use null when no validation was performed.

Critical Rules:
- If you find real email examples, use them to form the pattern and put them in `ejemplo_emails`.
- If you CANNOT find real email examples on primary sources, you ARE ALLOWED to use patterns derived from Business Intelligence platforms (e.g. RocketReach, SignalHire, Apollo) for your `formula_dominante` and `ord_email_patterns`.
- Do not set formula_dominante to "No detectada" if a trusted 3rd-party platform provides a highly probable pattern.
- ord_email_patterns.formula: Array of [patron, confidence, recommended].
- ord_email_patterns.primary_pattern: The single best pattern. You can use 3rd-party intelligence to pick this if needed.
- ord_email_patterns.primary_confidence: 0-100. Lower the confidence slightly if based purely on 3rd-party data without verified examples.
- Colombian companies often use .com.co domains (e.g., ecopetrol.com.co).

- Colombian companies often use .com.co domains (e.g., ecopetrol.com.co).

Produce a complete output with EXACTLY these two sections before your JSON block:
1. **Executive Summary**: A high-level summary of the company, its size, industries, and overall background. DO NOT include "Reasoning" or "Analytical Process".
2. **Research and Report**: A combined section that details your summary of sources searched, key findings, and the comprehensive email pattern analysis.
   - When "Email Validation Results" appear in the findings, include a dedicated **Email Validation** subsection with the validation report (which emails were tested, delivery status).
   - STRICT RULE: Do not include a "References" or "Citations" section anywhere! No bracketed citations `[1]` in the text. No URLs listed at the bottom.

3. **JSON**: Structured output at the very end matching the schema above.
"""


def build_query(company: str, domain: str = None) -> str:
    domain_hint = f" Company domain: {domain}" if domain else " Discover the company's email domain from your research."
    return (
        f"Research the corporate email pattern for {company}, a Colombian company. "
        f"CRITICAL METHODOLOGY: DO NOT perform LinkedIn web searches. First, you MUST find the main official website of the company and search strictly WITHIN that main website for employee or executive names and contact pages. "
        f"If you cannot find clear patterns on the main website, fallback to searching business directories or trusted external sources (excluding LinkedIn). "
        f"Only look for generic department emails if you completely fail to find individual employee emails. "
        f"Derive the email format (e.g. first.last@domain, firstlast@domain) from actual examples you find. "
        f"If official sources are not found, you may strictly use data reported from 3rd-party Business Intelligence platforms (like RocketReach, SignalHire) to determine the pattern.{domain_hint}"
    )


def extract_json_from_report(report: str) -> dict | None:
    """Extract the full JSON (including ord_email_patterns) from the report."""
    # Look for ```json ... ``` block
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', report)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try to find raw JSON object in the report around `company_research` or `ord_email_patterns`
    brace_match = re.search(r'\{[\s\S]*"company_research"[\s\S]*\}', report)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def create_config(model: str | None = None):
    """LLM stack from .env; optional ``--model`` overrides all three model ids."""
    return create_default_config(search_provider="brightdata", model_override=model)


async def run_research(company: str, domain: str = None, max_iterations: int = 5, max_time: int = 10, model: str = None) -> tuple[str, dict | None]:
    """Run the research and return (report, extracted_json)."""
    query = build_query(company, domain)
    config = create_config(model=model)

    researcher = IterativeResearcher(
        max_iterations=max_iterations,
        max_time_minutes=max_time,
        verbose=True,
        tracing=False,
        config=config,
    )

    report = await researcher.run(
        query,
        output_length="3-5 pages",
        output_instructions=OUTPUT_INSTRUCTIONS,
    )

    extracted = extract_json_from_report(report)
    return report, extracted


def save_to_mongodb(company_name: str, report_md: str, extracted: dict | None):
    """Save the research results to MongoDB."""
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    db_name = os.getenv("MONGO_DB_NAME", "deep_research_db")
    
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        # Attempt to get server info to check connection
        client.server_info()
        db = client[db_name]
        
        now = datetime.now(timezone.utc)
        base_doc = {
            "company_name": company_name,
            "inserted_at": now,
        }

        # 1. Save Company Research
        if extracted and "company_research" in extracted:
            company_doc = {**base_doc, **extracted["company_research"]}
            db.company_research.insert_one(company_doc)
            print("Successfully saved company_research to MongoDB.")

        # 2. Save Employees
        if extracted and "employees" in extracted:
            emp_doc = {**base_doc, "employees": extracted["employees"]}
            db.employees.insert_one(emp_doc)
            print("Successfully saved employees to MongoDB.")

        # 3. Save Email Patterns
        if extracted:
            email_doc = {
                **base_doc,
                "metadata": extracted.get("metadata", {}),
                "formula_dominante": extracted.get("formula_dominante", ""),
                "detalles": extracted.get("detalles", []),
                "ejemplo_emails": extracted.get("ejemplo_emails", []),
                "ord_email_patterns": extracted.get("ord_email_patterns", {}),
                "email_validation": extracted.get("email_validation"),
            }
            db.email_patterns.insert_one(email_doc)
            print("Successfully saved email_patterns to MongoDB.")

        # 4. Save Raw Report
        report_doc = {**base_doc, "report_markdown": report_md}
        db.reports.insert_one(report_doc)
        print("Successfully saved markdown report to MongoDB.")

    except Exception as e:
        print(f"\n[Warning] Failed to save to MongoDB: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Deep research Colombian company email patterns")
    parser.add_argument("company", help="Company name (e.g. Ecopetrol, Bancolombia)")
    parser.add_argument("--domain", "-d", help="Company email domain (e.g. ecopetrol.com.co)")
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Override reasoning/main/fast model ids (default: from .env)",
    )
    parser.add_argument("--max-iterations", "-i", type=int, default=5, help="Max research iterations (default: 5)")
    parser.add_argument("--max-time", "-t", type=int, default=60, help="Max time in minutes (default: 60)")
    parser.add_argument("--output", "-o", help="Output file path (default: outputs/<company_slug>_report.md)")
    parser.add_argument("--json-only", action="store_true", help="Print only the extracted JSON")
    args = parser.parse_args()

    # Validate API keys
    brightdata_key = os.getenv("BRIGHTDATA_API_KEY")
    if not brightdata_key:
        print("Error: Set BRIGHTDATA_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    brightdata_unlocker_zone = os.getenv("BRIGHTDATA_UNLOCKER_ZONE") or os.getenv("BRIGHTDATA_ZONE")
    if not brightdata_unlocker_zone:
        print("Error: Set BRIGHTDATA_UNLOCKER_ZONE (or BRIGHTDATA_ZONE) in .env", file=sys.stderr)
        sys.exit(1)

    llm_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_key:
        print("Error: Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    model_display = args.model or REASONING_MODEL
    print(f"\n=== Email Pattern Research: {args.company} (model: {model_display}) ===\n")
    report, extracted = asyncio.run(run_research(
        args.company,
        domain=args.domain,
        max_iterations=args.max_iterations,
        max_time=args.max_time,
        model=args.model,
    ))

    if args.json_only and extracted:
        print(json.dumps(extracted, indent=2, ensure_ascii=False))
        return

    if args.json_only and not extracted:
        print("Could not extract JSON from report.", file=sys.stderr)
        sys.exit(1)

    # Save report
    slug = re.sub(r'[^\w\-]', '_', args.company.lower())[:50]
    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    out_path = args.output or (out_dir / f"{slug}_email_pattern_report.md")
    out_path = Path(out_path)
    out_path.write_text(report, encoding="utf-8")
    print(f"\n=== Report saved to {out_path} ===\n")

    # Save JSON if extracted
    if extracted:
        # 1. Email Patterns & Metadata
        email_data = {
            "metadata": extracted.get("metadata", {}),
            "formula_dominante": extracted.get("formula_dominante", ""),
            "detalles": extracted.get("detalles", []),
            "ejemplo_emails": extracted.get("ejemplo_emails", []),
            "ord_email_patterns": extracted.get("ord_email_patterns", {}),
            "email_validation": extracted.get("email_validation"),
        }
        json_path_emails = out_path.with_suffix(".json")
        json_path_emails.write_text(json.dumps(email_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Emails JSON saved to {json_path_emails}")
        
        # 2. Employees Details
        if "employees" in extracted:
            json_path_employees = out_dir / f"{slug}_employees.json"
            json_path_employees.write_text(json.dumps(extracted["employees"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Employees JSON saved to {json_path_employees}")

        # 3. Company Research
        if "company_research" in extracted:
            json_path_company = out_dir / f"{slug}_company_research.json"
            json_path_company.write_text(json.dumps(extracted["company_research"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Company Research JSON saved to {json_path_company}")

        if "ord_email_patterns" in email_data:
            print("\nord_email_patterns (for database):")
            print(json.dumps(email_data["ord_email_patterns"], indent=2, ensure_ascii=False))

    # Save to MongoDB
    print("\n=== Saving Results to MongoDB ===")
    save_to_mongodb(args.company, report, extracted)

    print("\n=== Full Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
