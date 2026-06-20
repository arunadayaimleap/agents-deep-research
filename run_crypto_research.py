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

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")
os.environ.setdefault("SEARCH_PROVIDER", "openrouter")

from deep_researcher import IterativeResearcher, LLMConfig
from deep_researcher.tools.openrouter_server_tools import openrouter_datetime
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

Your response MUST have two sections in this order:

1. **Report** (## Report):
   A crypto market intelligence briefing focused on **actionable trade signals for the research date**. Structure:

   ### Executive Summary
   - Market tone today (risk-on/off), dominant movers, and 2–4 paragraphs on what matters for traders.

   ### Top Coins Today
   Table or list of leading coins discovered for {research_date} (symbol, name, approximate rank/market cap tier, 24h move if known).

   ### Tradability Screen
   Which coins passed reliability filters (liquidity, major exchange presence, volume) and which were excluded with brief reasons.

   ### Price Signal Analysis
   For each shortlisted coin (up to {max_coins}), subsection:
   #### [SYMBOL] — [Name]
   - **Trend:** bullish / bearish / neutral
   - **Key levels:** support, resistance, recent range
   - **Indicators:** RSI, MACD, moving averages, volume — cite values or ranges when found
   - **Catalysts:** news or events for {research_date}
   - **Signal strength:** strong / moderate / weak with one-line rationale
   - **Sources:** inline [n] markers

   ### Top Trade Signals for the Day
   Ranked list (best first) of up to {max_coins} setups:
   - Symbol, direction (long/short/neutral/watch), thesis, key levels, invalidation/risk, confidence (high/medium/low)
   - **Not financial advice** — research summary only.

   ### Risk & Limitations
   - Data delays, conflicting TA, low liquidity warnings, disclaimer.

   **Rules:**
   - Ground claims in findings; say "approximately" when exact numbers are unavailable.
   - Cite [1], [2], … and include **References** with URLs.
   - Prefer CoinGecko, CoinMarketCap, major exchange data, TradingView, reputable crypto news.

2. **JSON Output** (## JSON Output):
   Valid JSON only in a ```json code block:

```json
{{
  "metadata": {{
    "research_datetime": "{dt_info.get('datetime', '')}",
    "timezone": "{dt_info.get('timezone', 'UTC')}",
    "research_date": "{research_date}",
    "max_coins_requested": {max_coins},
    "total_coins_screened": 0,
    "total_trade_signals": 0,
    "total_sources_reviewed": 0,
    "sources": []
  }},
  "top_coins_today": [
    {{
      "rank": 1,
      "symbol": "BTC",
      "name": "",
      "market_cap_tier": "large | mid | small",
      "approx_24h_change": "",
      "tradable": true,
      "excluded_reason": null
    }}
  ],
  "price_signals": [
    {{
      "symbol": "",
      "trend": "bullish | bearish | neutral",
      "rsi": "",
      "macd": "",
      "support_levels": [],
      "resistance_levels": [],
      "volume_note": "",
      "catalysts": [],
      "signal_strength": "strong | moderate | weak",
      "source_urls": []
    }}
  ],
  "top_trade_signals": [
    {{
      "rank": 1,
      "symbol": "",
      "direction": "long | short | neutral | watch",
      "thesis": "",
      "entry_zone": "",
      "targets": [],
      "stop_invalidation": "",
      "confidence": "high | medium | low",
      "risk_notes": "",
      "source_urls": []
    }}
  ],
  "market_summary": "",
  "limitations": []
}}
```

Do not invent live prices. If exact numbers are missing, describe qualitative signals and note the gap.
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
        f"For {date_str}, identify the top cryptocurrencies of the day, filter to reliable tradable coins, "
        f"study their price signals, and select the best up to {max_coins} trade setups for the day.{dt_note} "
        f"Workflow: (1) list top coins by market cap and trending movers, "
        f"(2) exclude illiquid or unreliable tokens, "
        f"(3) gather technical and catalyst data per coin, "
        f"(4) rank trade signals with direction, levels, and confidence. "
        f"Use public market data and cited analysis only."
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
) -> tuple[str, dict | None, dict[str, str]]:
    dt_info = await openrouter_datetime(timezone=timezone)
    background = _format_datetime_context(dt_info)
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
    return report, extract_json_from_report(report), dt_info


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

    label = args.coin or f"top {args.max_coins} trade signals"
    print(f"\n=== Crypto Trade Research: {label} (model: {args.model}) ===\n")

    report, extracted, dt_info = asyncio.run(
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
