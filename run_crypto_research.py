#!/usr/bin/env python3
"""
Crypto trading signal research: top coins of the day → tradability filter → price signals → ranked trade setups.

Usage:
  python run_crypto_research.py
  python run_crypto_research.py --max-coins 5 --timezone America/New_York
  python run_crypto_research.py --coin BTC

Requires .env: OPENROUTER_API_KEY (LLM + openrouter:web_search / web_fetch / datetime).
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")
os.environ.setdefault("SEARCH_PROVIDER", "openrouter")

from deep_researcher import IterativeResearcher, LLMConfig
from deep_researcher.llm_config import config_model_summary, create_runner_config
from deep_researcher.tools.crypto_screening import (
    build_market_snapshot,
    format_trader_summary_table,
    inject_trader_summary,
    snapshot_to_context,
    snapshot_to_json,
)
from deep_researcher.tools.openrouter_server_tools import openrouter_datetime
from agents import set_tracing_disabled

if not os.getenv("OPENAI_API_KEY") or "your-" in str(os.getenv("OPENAI_API_KEY", "")):
    set_tracing_disabled(True)


def create_config(model: str | None = None) -> LLMConfig:
    return create_runner_config(model, search_provider="openrouter")


def _format_datetime_context(dt_info: dict[str, str]) -> str:
    return (
        f"Research datetime (OpenRouter): {dt_info.get('datetime', 'unknown')} "
        f"({dt_info.get('timezone', 'UTC')}). "
        f"Weekday: {dt_info.get('weekday') or 'n/a'}. "
        f"Date: {dt_info.get('date') or 'n/a'}. "
        f"Time: {dt_info.get('time') or 'n/a'}."
    )


def _get_output_instructions(max_coins: int, dt_info: dict[str, str]) -> str:
    dt_line = _format_datetime_context(dt_info)
    research_date = dt_info.get("date") or dt_info.get("datetime", "")[:10] or "today"
    return f"""
**{dt_line}**
**Maximum coins to analyze in depth: {max_coins}**

IMPORTANT: An AUTHORITATIVE BINANCE MARKET SNAPSHOT is in BACKGROUND CONTEXT with pre-scored rankings,
multi-timeframe (1d+4h) indicators, and tradability filter results. Use those exact numbers.
Volume ratios use 24h ticker volume vs 20-day completed daily average (NOT partial daily candles).

Your response MUST have two sections in this order:

1. **Report** (## Report):
   (A Trader Summary table is injected automatically — do not duplicate it.)

   ### Executive Summary — market tone, movers, risks (2–4 paragraphs).

   ### Top Coins Today — table with 24h volume rank, % change, tradability.

   ### Tradability Screen — explain hard filter pass/fail from snapshot.

   ### Price Signal Analysis — one subsection per ranked coin (snapshot order):
   - Score 0–100, trend 1d/4h, RSI, MACD, volume_24h_vs_avg_ratio, levels, catalysts.

   ### Top Trade Signals for the Day — rank EXACTLY as snapshot scores; all {max_coins} actionable with R:R.

   ### Risk & Limitations

2. **JSON Output** (## JSON Output): valid ```json block with trader_summary and top_trade_signals.

Rules: do not contradict snapshot numbers; do not re-rank; cite sources for catalysts only.
Research date: {research_date}
"""


def build_crypto_query(
    *,
    max_coins: int = 5,
    coin_hint: str | None = None,
    dt_info: dict[str, str] | None = None,
) -> str:
    dt = dt_info or {}
    date_str = dt.get("date") or (dt.get("datetime") or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    dt_note = f" Use research datetime {dt.get('datetime', date_str)} ({dt.get('timezone', 'UTC')}) for all 'today' references."
    if coin_hint:
        return (
            f"Research {coin_hint} as a crypto trading candidate for {date_str}.{dt_note} "
            f"Discover its rank among top coins, assess tradability (liquidity, exchange listings), "
            f"study price signals (trend, RSI, MACD, support/resistance, volume, catalysts), "
            f"and produce a trade signal recommendation with risk notes. "
            f"This is market research, not financial advice."
        )
    return (
        f"For {date_str}, produce a trade-signal briefing for the top {max_coins} coins.{dt_note} "
        f"A pre-computed Binance snapshot (tradability filter, multi-timeframe signals, numeric scores, "
        f"entry/stop/target/R:R) is in BACKGROUND CONTEXT — use it as the ranking source of truth. "
        f"Your job: add catalyst context from news search, explain each setup, and write the report. "
        f"Do not re-rank coins differently from the snapshot scores."
    )


def extract_json_from_report(report: str) -> dict | None:
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", report)
    if json_match:
        raw = json_match.group(1).strip()
        raw = re.sub(r"\\\(\s*(\d+)\s*\\\)", r"\1", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    for key in ("top_trade_signals", "price_signals", "top_coins_today"):
        brace_match = re.search(rf"\{{[\s\S]*\"{key}\"[\s\S]*\}}", report)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.lower())[:40]


def _timestamped_basename(coin_hint: str | None = None) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if coin_hint:
        return f"crypto_{_slug(coin_hint)}_{ts}"
    return f"crypto_trade_signals_{ts}"


async def run_research(
    *,
    max_coins: int = 5,
    coin_hint: str | None = None,
    timezone: str = "UTC",
    max_iterations: int = 5,
    max_time: int = 45,
    model: str | None = None,
) -> tuple[str, dict | None, dict[str, str], dict[str, Any]]:
    dt_info = await openrouter_datetime(timezone=timezone)

    print("\n=== Fetching Binance market snapshot (tradability + scoring) ===\n")
    snapshot = await build_market_snapshot(max_coins=max_coins, coin_hint=coin_hint)
    summary_table = format_trader_summary_table(snapshot["ranked_signals"])
    for i, row in enumerate(snapshot["ranked_signals"], 1):
        lv = row["levels"]
        rr = lv.get("risk_reward_t1")
        rr_s = f"{rr:.2f}:1" if rr else "n/a"
        print(
            f"  {i}. {row['base']} score={row['score']['total']} "
            f"{lv['direction']} entry=${lv['entry']} R:R={rr_s}"
        )
    print(f"\n  Excluded: {len(snapshot['excluded'])} coins (tradability filter)\n")

    background = _format_datetime_context(dt_info) + "\n\n" + snapshot_to_context(snapshot)
    query = build_crypto_query(max_coins=max_coins, coin_hint=coin_hint, dt_info=dt_info)
    config = create_config(model=model)
    researcher = IterativeResearcher(
        max_iterations=max_iterations,
        max_time_minutes=max_time,
        verbose=True,
        tracing=False,
        config=config,
        research_domain="crypto",
    )
    report = await researcher.run(
        query,
        output_length="4-8 pages",
        output_instructions=_get_output_instructions(max_coins, dt_info),
        background_context=background,
    )
    report = inject_trader_summary(report, summary_table)

    extracted = extract_json_from_report(report)
    snapshot_json = snapshot_to_json(snapshot, dt_info, max_coins)
    if extracted:
        extracted["trader_summary"] = snapshot_json.get("trader_summary", extracted.get("trader_summary"))
        extracted.setdefault("metadata", {}).update(snapshot_json.get("metadata", {}))
    else:
        extracted = snapshot_json

    return report, extracted, dt_info, snapshot


def main():
    parser = argparse.ArgumentParser(
        description="Crypto trading signal research for top coins of the day"
    )
    parser.add_argument(
        "--max-coins",
        "-n",
        type=int,
        default=5,
        help="Number of top coins / trade signals to cover (default: 5)",
    )
    parser.add_argument(
        "--coin",
        "-c",
        help="Research a specific coin symbol or name (e.g. BTC, Ethereum)",
    )
    parser.add_argument(
        "--timezone",
        "-z",
        default="UTC",
        help="IANA timezone for OpenRouter datetime (default: UTC)",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Override all LLM slots (default: REASONING/MAIN/FAST_MODEL from .env)",
    )
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

    config_preview = create_config(args.model)
    models_label = config_model_summary(config_preview)
    label = args.coin or f"top {args.max_coins} trade signals"
    print(f"\n=== Crypto Trade Research: {label} (models: {models_label}) ===\n")

    report, extracted, dt_info, _snapshot = asyncio.run(
        run_research(
            max_coins=args.max_coins,
            coin_hint=args.coin,
            timezone=args.timezone,
            max_iterations=args.max_iterations,
            max_time=args.max_time,
            model=args.model,
        )
    )

    print(f"\n=== Research datetime: {dt_info.get('datetime')} ({dt_info.get('timezone')}) ===\n")

    if args.json_only and extracted:
        print(json.dumps(extracted, indent=2, ensure_ascii=False))
        return
    if args.json_only and not extracted:
        print("Could not extract JSON from report.", file=sys.stderr)
        sys.exit(1)

    out_dir = _project_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    base = _timestamped_basename(args.coin)
    out_path = Path(args.output) if args.output else (out_dir / f"{base}.md")
    out_path.write_text(report, encoding="utf-8")
    print(f"\n=== Report saved to {out_path} ===\n")

    if extracted:
        json_path = out_path.with_suffix(".json")
        json_path.write_text(
            json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"JSON saved to {json_path}")
        if "top_trade_signals" in extracted:
            print("\nTop trade signals (JSON):")
            print(json.dumps(extracted["top_trade_signals"], indent=2, ensure_ascii=False))

    print("\n=== Full Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
