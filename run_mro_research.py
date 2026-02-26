#!/usr/bin/env python3
"""
Run deep MRO (Maintenance, Repair, Overhaul) research on aircraft–engine–supplier configurations.
Output: reasoning + research + report + JSON (saved to outputs/).

Usage:
  python run_mro_research.py "Boeing 737-800" "CFM56-7B" "CFM International"
  python run_mro_research.py "Boeing 737-800" "CFM56-7B" "CFM International" --context "Global MRO demand outlook"
  python run_mro_research.py "A320" "V2500" "IAE" -i 5 -t 15

Requires .env with OPENROUTER_API_KEY and SERPER_API_KEY.
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


# Output instructions for the MRO deep research agent (matches prompts/mro_research.txt)
OUTPUT_INSTRUCTIONS = """
Your response MUST have four distinct sections in this order:

1. **Reasoning** (## Reasoning):
   Explain your analytical approach:
   - How you validated aircraft–engine compatibility
   - What sources you searched
   - How you evaluated incident signals
   - How you assessed regulatory and supplier exposure
   - Any data gaps or uncertainty limitations

2. **Research Summary** (## Research):
   Summarize:
   - Fleet size and age findings
   - Incident / SDR signals
   - Regulatory directives identified
   - Supplier risk signals
   - Key external intelligence sources
   Include real URLs where applicable.

3. **Report** (## Report):
   A comprehensive markdown intelligence report including:
   - Configuration Validation
   - Fleet Exposure Overview
   - Incident & SDR Trends
   - Regulatory Directive Signals
   - Supplier Risk Assessment
   - Repair Risk Outlook (Qualitative)
   - MRO Implications
   - Confidence Assessment

   Use citation markers [1], [2], etc.
   Include references at the end.

4. **JSON Output** (## JSON Output):
   A valid JSON block that can be parsed.
   It MUST match this schema:
{
  "metadata": {
    "aircraft": "...",
    "engine": "...",
    "supplier": "...",
    "analysis_scope": "public intelligence research",
    "total_sources_reviewed": N,
    "sources": []
  },
  "compatibility": {
    "valid_configuration": true,
    "notes": "",
    "confidence": "high | medium | low"
  },
  "fleet_exposure": {
    "fleet_size_estimate": 0,
    "average_age_estimate": 0,
    "trend": "stable | aging | declining | growing",
    "confidence": "high | medium | low"
  },
  "incident_signals": {
    "trend_direction": "increasing | stable | declining | unclear",
    "recurring_issues": [],
    "signal_level": "low | moderate | elevated | high",
    "confidence": "high | medium | low"
  },
  "regulatory_signals": {
    "directive_activity": "low | moderate | high",
    "trend": "increasing | stable | declining",
    "confidence": "high | medium | low"
  },
  "supplier_risk": {
    "overall_risk_level": "low | moderate | elevated | high",
    "drivers": [],
    "confidence": "high | medium | low"
  },
  "repair_risk_assessment": {
    "short_term_outlook": "low | moderate | elevated | high | unclear",
    "medium_term_outlook": "stable | increasing | declining | unclear",
    "primary_drivers": [],
    "confidence": "high | medium | low"
  }
}

If compatibility is invalid, clearly state it and set repair_risk_assessment.short_term_outlook to "unclear".

Do NOT fabricate quantitative probabilities.
Use qualitative classifications if precise data unavailable.
"""


def build_mro_query(aircraft: str, engine: str, supplier: str, context: str = None) -> str:
    context_part = f" Context: {context}" if context else ""
    return (
        f"Conduct deep public research on repair risk signals for the configuration: "
        f"{aircraft} powered by {engine}, supplied by {supplier}. "
        f"Validate compatibility first. "
        f"Then analyze fleet exposure, public incident trends (FAA SDR, NTSB, EASA, industry reports), "
        f"regulatory directives (ADs), supplier disruption signals, and global maintenance patterns. "
        f"Assess qualitative short-term and medium-term repair risk for MRO planning purposes. "
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


async def run_research(
    aircraft: str,
    engine: str,
    supplier: str,
    context: str = None,
    max_iterations: int = 5,
    max_time: int = 10,
    model: str = None,
) -> tuple[str, dict | None]:
    """Run the MRO research and return (report, extracted_json)."""
    query = build_mro_query(aircraft, engine, supplier, context)
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
        output_instructions=OUTPUT_INSTRUCTIONS,
    )

    extracted = extract_json_from_report(report)
    return report, extracted


def main():
    parser = argparse.ArgumentParser(description="Deep MRO research on aircraft–engine–supplier configurations")
    parser.add_argument("aircraft", help="Aircraft model (e.g. Boeing 737-800, A320)")
    parser.add_argument("engine", help="Engine model (e.g. CFM56-7B, V2500)")
    parser.add_argument("supplier", help="Engine supplier (e.g. CFM International, IAE)")
    parser.add_argument("--context", "-c", help="Optional context (e.g. Global MRO demand outlook)")
    parser.add_argument("--model", "-m", default="deepseek/deepseek-v3.2", help="LLM model")
    parser.add_argument("--max-iterations", "-i", type=int, default=5, help="Max research iterations (default: 5)")
    parser.add_argument("--max-time", "-t", type=int, default=10, help="Max time in minutes (default: 10)")
    parser.add_argument("--output", "-o", help="Output file path (default: outputs/<slug>_mro_report.md)")
    parser.add_argument("--json-only", action="store_true", help="Print only the extracted JSON")
    args = parser.parse_args()

    if not os.getenv("SERPER_API_KEY"):
        print("Error: Set SERPER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Error: Set OPENROUTER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    slug = f"{_slug(args.aircraft)}_{_slug(args.engine)}_{_slug(args.supplier)}"
    print(f"\n=== MRO Research: {args.aircraft} / {args.engine} / {args.supplier} (model: {args.model}) ===\n")

    report, extracted = asyncio.run(run_research(
        args.aircraft,
        args.engine,
        args.supplier,
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
    out_path = Path(args.output) if args.output else (out_dir / f"{slug}_mro_report.md")
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
