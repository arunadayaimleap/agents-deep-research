#!/usr/bin/env python3
"""
Deep research on top criminal cases in the news today.
Output: markdown report + structured JSON (saved to outputs/).

Usage:
  python run_crime_research.py
  python run_crime_research.py --region US --max-cases 5
  python run_crime_research.py --case "UnitedHealth shooting suspect" --region US

Requires .env: OPENROUTER_API_KEY (LLM + openrouter:web_search / openrouter:web_fetch).
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")
os.environ.setdefault("SEARCH_PROVIDER", "openrouter")

from deep_researcher import IterativeResearcher, LLMConfig
from agents import set_tracing_disabled

if not os.getenv("OPENAI_API_KEY") or "your-" in str(os.getenv("OPENAI_API_KEY", "")):
    set_tracing_disabled(True)


def create_config(model: str | None = None) -> LLMConfig:
    m = model or "deepseek/deepseek-v3.2"
    return LLMConfig(
        search_provider="openrouter",
        reasoning_model_provider="openrouter",
        reasoning_model=m,
        main_model_provider="openrouter",
        main_model=m,
        fast_model_provider="openrouter",
        fast_model=m,
    )


def _get_output_instructions(max_cases: int, region: str | None) -> str:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S %Z")
    region_note = region or "international / multi-region as warranted by the news cycle"
    return f"""
**Current date and time: {date_str} {time_str}**
**Target region focus: {region_note}**
**Maximum cases to cover in depth: {max_cases}**

Your response MUST have two sections in this order:

1. **Report** (## Report):
   A criminal-case intelligence briefing for news consumers and analysts. Structure:

   ### Executive Summary
   - What is dominating crime news today and why it matters (2–4 paragraphs).

   ### Top Cases Today
   For each of up to {max_cases} major cases (most prominent in today's news first), use a subsection:
   #### [Case headline / short name]
   - **Status:** (investigation, arrest, trial, sentencing, appeal, etc.)
   - **Jurisdiction:** country, state/province, city where known
   - **Key parties:** victims, suspects/defendants, agencies, courts
   - **Alleged offenses / charges:** be precise; say "reportedly" when unconfirmed
   - **Timeline:** dated bullet points of known events
   - **What is publicly known vs disputed**
   - **Why it is top news today**
   - **Sources:** inline [n] markers

   ### Cross-Case Themes
   Brief note on patterns (e.g. organized crime, white-collar, violent crime trends) only if supported by today's coverage.

   ### Limitations
   - Note where reporting conflicts, where identity is protected, or where only allegations exist.

   **Rules:**
   - Use only public reporting; do not present allegations as proven facts.
   - Cite [1], [2], … and include a **References** list with URLs at the end.
   - Prefer reputable news wires, court records, and official statements over social media rumors.

2. **JSON Output** (## JSON Output):
   Valid JSON only in a ```json code block:

```json
{{
  "metadata": {{
    "research_date": "{date_str}",
    "region_focus": "{region or 'global'}",
    "max_cases_requested": {max_cases},
    "total_cases_reported": 0,
    "total_sources_reviewed": 0,
    "sources": []
  }},
  "top_cases": [
    {{
      "rank": 1,
      "headline": "",
      "short_name": "",
      "jurisdiction": "",
      "status": "",
      "key_parties": [],
      "charges_or_offenses": [],
      "timeline": [{{"date": "YYYY-MM-DD", "event": ""}}],
      "why_top_news_today": "",
      "confidence": "high | medium | low",
      "source_urls": []
    }}
  ],
  "themes": [],
  "limitations": []
}}
```

Do not invent case details. If fewer than {max_cases} major cases are found in today's news, report only what is substantiated.
"""


def build_crime_query(
    *,
    region: str | None = None,
    max_cases: int = 5,
    case_hint: str | None = None,
) -> str:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    region_part = f" Focus on {region}." if region else ""
    if case_hint:
        return (
            f"Research the criminal case in the news related to: {case_hint}. "
            f"Use today's date ({date_str}) for recency.{region_part} "
            f"Gather facts from public news, court filings, and official statements. "
            f"Build a structured briefing: parties, charges, timeline, current status, and why it is in the news. "
            f"Do not treat allegations as convictions."
        )
    return (
        f"Identify and deeply research the top {max_cases} criminal cases dominating news today ({date_str}).{region_part} "
        f"Use current web search results from major news outlets and official sources. "
        f"For each case: jurisdiction, key parties, charges/offenses, timeline, investigation or trial status, "
        f"and why it is leading coverage today. "
        f"Rank by news prominence and public impact. "
        f"Only use verifiable public information; label allegations clearly."
    )


def extract_json_from_report(report: str) -> dict | None:
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", report)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace_match = re.search(r"\{[\s\S]*\"top_cases\"[\s\S]*\}", report)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.lower())[:40]


def _timestamped_basename(region: str | None = None, case_hint: str | None = None) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if case_hint:
        return f"crime_{_slug(case_hint)}_{ts}"
    reg = _slug(region) if region else "global"
    return f"crime_top_cases_{reg}_{ts}"


async def run_research(
    *,
    region: str | None = None,
    max_cases: int = 5,
    case_hint: str | None = None,
    max_iterations: int = 5,
    max_time: int = 45,
    model: str | None = None,
) -> tuple[str, dict | None]:
    query = build_crime_query(region=region, max_cases=max_cases, case_hint=case_hint)
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
        output_length="4-8 pages",
        output_instructions=_get_output_instructions(max_cases, region),
    )
    return report, extract_json_from_report(report)


def main():
    parser = argparse.ArgumentParser(
        description="Deep research on top criminal cases in today's news"
    )
    parser.add_argument(
        "--region",
        "-r",
        help="Geographic focus (e.g. US, UK, Colombia, global)",
    )
    parser.add_argument(
        "--max-cases",
        "-n",
        type=int,
        default=5,
        help="Number of top cases to cover (default: 5)",
    )
    parser.add_argument(
        "--case",
        "-c",
        help="Research a specific case by name/headline instead of top-N list",
    )
    parser.add_argument("--model", "-m", default="deepseek/deepseek-v3.2")
    parser.add_argument("--max-iterations", "-i", type=int, default=5)
    parser.add_argument("--max-time", "-t", type=int, default=45)
    parser.add_argument("--output", "-o")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    if not (
        os.getenv("OPENROUTER_API_KEY")
        or os.getenv("DR_OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    ):
        print("Error: Set OPENROUTER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    label = args.case or f"top {args.max_cases} cases ({args.region or 'global'})"
    print(f"\n=== Crime Research: {label} (model: {args.model}) ===\n")

    report, extracted = asyncio.run(
        run_research(
            region=args.region,
            max_cases=args.max_cases,
            case_hint=args.case,
            max_iterations=args.max_iterations,
            max_time=args.max_time,
            model=args.model,
        )
    )

    if args.json_only and extracted:
        print(json.dumps(extracted, indent=2, ensure_ascii=False))
        return
    if args.json_only and not extracted:
        print("Could not extract JSON from report.", file=sys.stderr)
        sys.exit(1)

    out_dir = _project_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    base = _timestamped_basename(args.region, args.case)
    out_path = Path(args.output) if args.output else (out_dir / f"{base}.md")
    out_path.write_text(report, encoding="utf-8")
    print(f"\n=== Report saved to {out_path} ===\n")

    if extracted:
        json_path = out_path.with_suffix(".json")
        json_path.write_text(
            json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON saved to {json_path}")
        if "top_cases" in extracted:
            print("\nTop cases (JSON):")
            print(json.dumps(extracted["top_cases"], indent=2, ensure_ascii=False))

    print("\n=== Full Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
