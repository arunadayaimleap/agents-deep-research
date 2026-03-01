#!/usr/bin/env python3
"""
Run deep MRO (Maintenance, Repair, Overhaul) research on aircraft–part configurations.
Output: report + JSON (saved to outputs/).

Usage:
  python run_mro_research.py "Boeing 737-800" "engine"
  python run_mro_research.py "Boeing 737-800" "engine" --make "CFM56-7B"
  python run_mro_research.py "A320" "wing" --make "Airbus" --context "Global MRO demand outlook"

Requires .env with OPENROUTER_API_KEY and SERPER_API_KEY.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from deep_researcher import IterativeResearcher, LLMConfig
from agents import set_tracing_disabled

# Disable tracing when OPENAI_API_KEY is placeholder (avoids 401; we use OpenRouter)
if not os.getenv("OPENAI_API_KEY") or "your-" in str(os.getenv("OPENAI_API_KEY", "")):
    set_tracing_disabled(True)


def create_config(model: str = None) -> LLMConfig:
    """Same as email script: explicit OpenRouter config."""
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


def _get_output_instructions() -> str:
    """Build output instructions with current date/time."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S %Z")
    return f"""
**Current date and time for this analysis: {date_str} {time_str}**

Your response MUST have two distinct sections in this order:

1. **Report** (## Report):
   A comprehensive markdown intelligence report including:
   - Configuration Validation
   - Fleet Exposure Overview
   - Incident & SDR Trends
   - Regulatory Directive Signals
   - Supplier Risk Assessment
   - Repair Risk Outlook (Qualitative)
   - MRO Implications
   - Confidence Assessment
   - **Final Actionable Points** (numbered list of concrete recommendations for MRO planning)

   **Requirements:**
   - Include specific figures, numbers, and statistics wherever available (fleet counts, AD counts, incident numbers, age ranges, etc.).
   - Use markdown tables to summarize key data (e.g. fleet metrics, AD summary, incident trends).
   - Cite every claim with markers [1], [2], etc. and provide a full references list with URLs at the end.
   - Do NOT invent numbers; use "approximately" or qualitative terms only when precise data is unavailable.

2. **JSON Output** (## JSON Output):
   A valid JSON block that can be parsed.
   It MUST match this schema:
{{
  "metadata": {{
    "aircraft": "...",
    "part": "...",
    "make": "..." or null,
    "analysis_scope": "public intelligence research",
    "total_sources_reviewed": N,
    "sources": []
  }},
  "compatibility": {{
    "valid_configuration": true,
    "notes": "",
    "confidence": "high | medium | low"
  }},
  "fleet_exposure": {{
    "fleet_size_estimate": 0,
    "average_age_estimate": 0,
    "trend": "stable | aging | declining | growing",
    "confidence": "high | medium | low"
  }},
  "incident_signals": {{
    "trend_direction": "increasing | stable | declining | unclear",
    "recurring_issues": [],
    "signal_level": "low | moderate | elevated | high",
    "confidence": "high | medium | low"
  }},
  "regulatory_signals": {{
    "directive_activity": "low | moderate | high",
    "trend": "increasing | stable | declining",
    "confidence": "high | medium | low"
  }},
  "supplier_risk": {{
    "overall_risk_level": "low | moderate | elevated | high",
    "drivers": [],
    "confidence": "high | medium | low"
  }},
  "repair_risk_assessment": {{
    "short_term_outlook": "low | moderate | elevated | high | unclear",
    "medium_term_outlook": "stable | increasing | declining | unclear",
    "primary_drivers": [],
    "confidence": "high | medium | low"
  }}
}}

If compatibility is invalid, clearly state it and set repair_risk_assessment.short_term_outlook to "unclear".

Do NOT fabricate quantitative probabilities.
Use qualitative classifications if precise data unavailable.
"""


def get_output_instructions() -> str:
    return _get_output_instructions()


def build_mro_query(aircraft: str, part: str, make: str | None = None, context: str | None = None) -> str:
    now = datetime.now()
    date_time_str = now.strftime("%Y-%m-%d %H:%M")
    context_part = f" Context: {context}" if context else ""
    return (
        f"Conduct deep public research on repair risk signals for the configuration: "
        f"{aircraft} {part}. "
        f"{f'Specific make/model: {make}. ' if make else 'Specific make/model unknown - research common options for this aircraft. '}"
        f"Analysis date: {date_time_str}. "
        f"Validate compatibility first. "
        f"Then analyze fleet exposure, public incident trends (FAA SDR, NTSB, EASA, industry reports), "
        f"regulatory directives (ADs), supplier disruption signals, and global maintenance patterns. "
        f"Assess qualitative short-term and medium-term repair risk for MRO planning purposes. "
        f"Include specific figures, statistics, tables, and citations. "
        f"Do NOT invent probabilities. Base findings only on real public sources."
        f"{context_part}"
    )


def extract_json_from_report(report: str) -> dict | None:
    """Extract the MRO JSON from the report."""
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', report)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace_match = re.search(r'\{[\s\S]*"repair_risk_assessment"[\s\S]*\}', report)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None




def _slug(s: str) -> str:
    return re.sub(r'[^\w\-]', '_', s.lower())[:30]


def _timestamped_basename(aircraft: str, part: str, make: str | None = None) -> str:
    """Generate timestamped basename for outputs, e.g. boeing_737-800_engine_cfm56-7b_mro_report_2025-01-30_14-30-00"""
    make_slug = _slug(make) if make else "unknown"
    slug = f"{_slug(aircraft)}_{_slug(part)}_{make_slug}"
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{slug}_mro_report_{ts}"


async def run_research(
    aircraft: str,
    part: str,
    make: str | None = None,
    context: str | None = None,
    max_iterations: int = 5,
    max_time: int = 60,
    model: str | None = None,
) -> tuple[str, dict | None]:
    """Run the MRO research and return (report, extracted_json)."""
    query = build_mro_query(aircraft, part, make, context)
    # Same as email script: explicit OpenRouter config (not create_default_config)
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
        output_length="5-8 pages",
        output_instructions=get_output_instructions(),
    )

    extracted = extract_json_from_report(report)
    return report, extracted


def main():
    parser = argparse.ArgumentParser(description="Deep MRO research on aircraft–part configurations")
    parser.add_argument("aircraft", help="Aircraft model (e.g. Boeing 737-800, A320)")
    parser.add_argument("part", help="Part type - generic term (e.g. engine, wing, airframe, landing gear)")
    parser.add_argument("--make", "-k", help="Make/model if known (e.g. CFM56-7B, CFM International)")
    parser.add_argument("--context", "-c", help="Optional context (e.g. Global MRO demand outlook)")
    parser.add_argument("--model", "-m", default="deepseek/deepseek-v3.2", help="LLM model")
    parser.add_argument("--max-iterations", "-i", type=int, default=5, help="Max research iterations (default: 5)")
    parser.add_argument("--max-time", "-t", type=int, default=60, help="Max time in minutes (default: 60)")
    parser.add_argument("--output", "-o", help="Output file path (default: outputs/<slug>_mro_report.md)")
    parser.add_argument("--json-only", action="store_true", help="Print only the extracted JSON")
    args = parser.parse_args()

    if not os.getenv("SERPER_API_KEY"):
        print("Error: Set SERPER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Error: Set OPENROUTER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    make_display = args.make or "unknown"
    print(f"\n=== MRO Research: {args.aircraft} / {args.part} / {make_display} (model: {args.model}) ===\n")

    report, extracted = asyncio.run(run_research(
        args.aircraft,
        args.part,
        make=args.make,
        context=args.context,
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

    out_dir = _project_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    base = _timestamped_basename(args.aircraft, args.part, args.make)
    out_path = Path(args.output) if args.output else (out_dir / f"{base}.md")
    out_path.write_text(report, encoding="utf-8")
    print(f"\n=== Report saved to {out_path} ===\n")

    if extracted:
        json_path = out_path.with_suffix(".json")
        json_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON saved to {json_path}")
        if "repair_risk_assessment" in extracted:
            print("\nRepair Risk Assessment:")
            print(json.dumps(extracted["repair_risk_assessment"], indent=2, ensure_ascii=False))

    print("\n=== Full Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
