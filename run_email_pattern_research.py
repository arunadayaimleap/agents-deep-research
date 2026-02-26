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


# Output instructions for the writer - must produce reasoning, research, report, and JSON
OUTPUT_INSTRUCTIONS = """
Your response MUST have four distinct sections in this order:

1. **Reasoning** (## Reasoning): Your analytical process. How you approached the research, what gaps you identified, and how you reached your conclusions about the email pattern.

2. **Research Summary** (## Research): Summary of sources you searched, key findings from each, and the real email addresses you discovered with their sources.

3. **Report** (## Report): A comprehensive markdown report with proper citations [1], [2], etc. Include references at the end.

4. **JSON Output** (## JSON Output): A valid JSON block that can be parsed. It MUST match this schema for ord_email_patterns:
{
  "metadata": {"empresa": "...", "nombre_fantasia": "...", "dominio": "...", "pais": "Colombia", "total_emails_encontrados": N, "fuentes": []},
  "formula_dominante": "first.last or No detectada",
  "detalles": [{"patron": "...", "confianza": 0-100, "es_recomendado": true/false, "frecuencia": N}],
  "ejemplo_emails": [{"email": "real@domain.co", "source": "https://..."}],
  "ord_email_patterns": {
    "formula": [["patron", confidence, recommended], ...],
    "primary_pattern": "best pattern or No detectada",
    "primary_confidence": 0-100
  }
}

If you found NO real emails, use formula_dominante: "No detectada", detalles: [], ejemplo_emails: [], ord_email_patterns.primary_pattern: "No detectada", primary_confidence: 0.
"""


def build_query(company: str, domain: str = None) -> str:
    domain_hint = f" Company domain: {domain}" if domain else " Discover the company's email domain from your research."
    return (
        f"Research the corporate email pattern for {company}, a Colombian company. "
        f"Find REAL employee email addresses from press releases, LinkedIn, company websites, news articles, and directories. "
        f"Derive the email format (e.g. first.last@domain, firstlast@domain) ONLY from actual examples you find. "
        f"Do not invent or guess - only report patterns supported by real emails.{domain_hint}"
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
    # Try to find raw JSON object in the report
    brace_match = re.search(r'\{[\s\S]*"ord_email_patterns"[\s\S]*\}', report)
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
        json_path = out_path.with_suffix(".json")
        json_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON saved to {json_path}")
        if "ord_email_patterns" in extracted:
            print("\nord_email_patterns (for database):")
            print(json.dumps(extracted["ord_email_patterns"], indent=2, ensure_ascii=False))

    print("\n=== Full Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
