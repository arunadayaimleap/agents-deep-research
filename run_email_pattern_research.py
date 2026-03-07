#!/usr/bin/env python3
"""
Run deep research on a Colombian company to discover its email pattern.
Output: reasoning + research + report + JSON (for ord_email_patterns).

Usage:
  python run_email_pattern_research.py "Ecopetrol"
  python run_email_pattern_research.py "Bancolombia" --domain bancolombia.com.co
  python run_email_pattern_research.py "Grupo Aval" --max-iterations 5 --max-time 15

Requires .env with OPEN_ROUTER_KEY and SERPER_DEV_API_KEY (or SERPER_API_KEY).
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
# Load .env from script directory so OPENROUTER_API_KEY is found
load_dotenv(_project_root / ".env")

from deep_researcher import IterativeResearcher, LLMConfig
from deep_researcher.llm_config import create_default_config


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
      "<industry 1>": ["<activity 1>", "<activity 2>"]
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
  }
}
```

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
   - STRICT RULE: Do not include a "References" or "Citations" section anywhere! No bracketed citations `[1]` in the text. No URLs listed at the bottom.

3. **JSON**: Structured output at the very end matching the schema above.
"""


def build_query(company: str, domain: str = None) -> str:
    domain_hint = f" Company domain: {domain}" if domain else " Discover the company's email domain from your research."
    return (
        f"Research the corporate email pattern for {company}, a Colombian company. "
        f"CRITICAL METHODOLOGY: You MUST begin by searching LinkedIn/web to find the names of top executives and employees. "
        f"Once you have a list of employee names and their positions, use those specific names in web searches to hunt down their direct corporate email addresses. "
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


def create_config(model: str = None) -> LLMConfig | None:
    """Create LLM config. Uses OpenRouter with specified model when OPENROUTER_API_KEY is set."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY")
    if not openrouter_key:
        return None
    m = model or "deepseek/deepseek-v3.2"
    return LLMConfig(
        search_provider="serper",
        reasoning_model_provider="openrouter",
        reasoning_model=m,
        main_model_provider="openrouter",
        main_model=m,
        fast_model_provider="openrouter",
        fast_model=m,
    )


async def run_research(company: str, domain: str = None, max_iterations: int = 5, max_time: int = 10, model: str = None) -> tuple[str, dict | None]:
    """Run the research and return (report, extracted_json)."""
    query = build_query(company, domain)
    config = create_config(model=model)
    if not config:
        raise RuntimeError(
            "OPENROUTER_API_KEY not found in .env. Set it to use OpenRouter (required for deepseek/deepseek-v3.2)."
        )

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


def main():
    parser = argparse.ArgumentParser(description="Deep research Colombian company email patterns")
    parser.add_argument("company", help="Company name (e.g. Ecopetrol, Bancolombia)")
    parser.add_argument("--domain", "-d", help="Company email domain (e.g. ecopetrol.com.co)")
    parser.add_argument("--model", "-m", default="deepseek/deepseek-v3.2", help="LLM model (default: deepseek/deepseek-v3.2)")
    parser.add_argument("--max-iterations", "-i", type=int, default=5, help="Max research iterations (default: 5)")
    parser.add_argument("--max-time", "-t", type=int, default=10, help="Max time in minutes (default: 10)")
    parser.add_argument("--output", "-o", help="Output file path (default: outputs/<company_slug>_report.md)")
    parser.add_argument("--json-only", action="store_true", help="Print only the extracted JSON")
    args = parser.parse_args()

    # Validate API keys
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        print("Error: Set SERPER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    llm_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_key:
        print("Error: Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Email Pattern Research: {args.company} (model: {args.model}) ===\n")
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
            "ord_email_patterns": extracted.get("ord_email_patterns", {})
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

    print("\n=== Full Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
