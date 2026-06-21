"""
Deterministic crypto tradability screening, signal scoring, and trader summary generation.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from .binance_tools import get_24hr, get_price_signals_bundle, get_top_symbols

MIN_QUOTE_VOLUME_24H = float(os.getenv("CRYPTO_MIN_QUOTE_VOLUME_24H", "50000000"))
MIN_KLINE_BARS = int(os.getenv("CRYPTO_MIN_KLINE_BARS", "30"))
TOP_POOL_SIZE = int(os.getenv("CRYPTO_TOP_POOL_SIZE", "25"))


def _confidence(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _direction(score: float, trend_1d: str, trend_4h: str) -> str:
    bearish = sum(1 for t in (trend_1d, trend_4h) if "bearish" in (t or ""))
    bullish = sum(1 for t in (trend_1d, trend_4h) if "bullish" in (t or ""))
    if score >= 58 and bullish >= bearish:
        return "long"
    if score <= 42 and bearish > bullish:
        return "short"
    if score >= 50:
        return "long"
    return "watch"


def compute_signal_score(bundle: dict[str, Any]) -> dict[str, Any]:
    """Score 0–100 from multi-timeframe Binance bundle (higher = stronger long bias)."""
    if bundle.get("error"):
        return {"total": 0, "breakdown": {}, "label": "unscored"}

    tf1d = (bundle.get("timeframes") or {}).get("1d") or {}
    tf4h = (bundle.get("timeframes") or {}).get("4h") or {}
    breakdown: dict[str, float] = {}
    score = 50.0  # neutral baseline

    trend_1d = tf1d.get("trend") or "neutral"
    if trend_1d == "bullish":
        breakdown["trend_1d"] = 12
    elif trend_1d == "bullish-leaning":
        breakdown["trend_1d"] = 6
    elif trend_1d == "bearish":
        breakdown["trend_1d"] = -12
    elif trend_1d == "bearish-leaning":
        breakdown["trend_1d"] = -6
    else:
        breakdown["trend_1d"] = 0

    trend_4h = tf4h.get("trend") or "neutral"
    if "bullish" in trend_4h:
        breakdown["trend_4h"] = 8
    elif "bearish" in trend_4h:
        breakdown["trend_4h"] = -8
    else:
        breakdown["trend_4h"] = 0

    rsi_1d = tf1d.get("rsi14")
    if rsi_1d is not None:
        if rsi_1d <= 35:
            breakdown["rsi_1d"] = 8
        elif rsi_1d >= 70:
            breakdown["rsi_1d"] = -8
        elif 45 <= rsi_1d <= 60:
            breakdown["rsi_1d"] = 4
        else:
            breakdown["rsi_1d"] = 0

    for key, tf, pts_pos, pts_neg in (
        ("macd_1d", tf1d, 10, -10),
        ("macd_4h", tf4h, 8, -8),
    ):
        hist = (tf.get("macd") or {}).get("histogram")
        if hist is not None:
            breakdown[key] = pts_pos if hist > 0 else pts_neg if hist < 0 else 0

    vol_ratio = bundle.get("volume_24h_vs_avg_ratio")
    if vol_ratio is not None:
        if vol_ratio >= 1.0:
            breakdown["volume_24h"] = 15
        elif vol_ratio >= 0.7:
            breakdown["volume_24h"] = 8
        elif vol_ratio >= 0.5:
            breakdown["volume_24h"] = 3
        else:
            breakdown["volume_24h"] = -10

    last = tf1d.get("last_close")
    sma20, sma50, sma200 = tf1d.get("sma20"), tf1d.get("sma50"), tf1d.get("sma200")
    if last and sma20 and sma50 and sma200:
        if last > sma20 > sma50 > sma200:
            breakdown["ma_stack"] = 18
        elif last > sma20 and sma20 >= sma50:
            breakdown["ma_stack"] = 10
        elif last < sma20 < sma50:
            breakdown["ma_stack"] = -10
        else:
            breakdown["ma_stack"] = 0

    score += sum(breakdown.values())
    score = max(0, min(100, round(score, 1)))
    label = "strong" if score >= 70 else "moderate" if score >= 55 else "weak"
    return {"total": score, "breakdown": breakdown, "label": label}


def passes_tradability(coin: dict[str, Any], bundle: dict[str, Any]) -> tuple[bool, str | None]:
    vol = float(coin.get("quote_volume_24h") or 0)
    if vol < MIN_QUOTE_VOLUME_24H:
        return False, f"24h quote volume ${vol:,.0f} below min ${MIN_QUOTE_VOLUME_24H:,.0f}"

    if bundle.get("error"):
        return False, bundle["error"]

    tf1d = (bundle.get("timeframes") or {}).get("1d") or {}
    bars = tf1d.get("candles_analyzed") or 0
    if bars < MIN_KLINE_BARS:
        return False, f"Only {bars} daily candles (min {MIN_KLINE_BARS})"

    return True, None


def compute_trade_levels(bundle: dict[str, Any], score_info: dict[str, Any]) -> dict[str, Any]:
    """Derive entry/stop/target and risk-reward from 4h levels (fallback 1d)."""
    tf4h = (bundle.get("timeframes") or {}).get("4h") or {}
    tf1d = (bundle.get("timeframes") or {}).get("1d") or {}
    tf = tf4h if tf4h.get("last_close") else tf1d

    last = float(tf.get("last_close") or bundle.get("ticker_24h", {}).get("last_price") or 0)
    support = float(tf.get("support") or tf1d.get("support") or 0)
    resistance = float(tf.get("resistance") or tf1d.get("resistance") or 0)

    trend_1d = tf1d.get("trend") or "neutral"
    trend_4h = tf4h.get("trend") or "neutral"
    direction = _direction(score_info["total"], trend_1d, trend_4h)

    entry = round(last, 6)

    if direction == "short":
        stop = round(resistance * 1.005, 6) if resistance else None
        target = round(support, 6) if support else None
        rr = None
        if stop and target and entry < stop and target < entry:
            risk = stop - entry
            reward = entry - target
            if risk > 0 and reward > 0:
                rr = round(reward / risk, 2)
    else:
        stop = round(support * 0.995, 6) if support else None
        target = round(resistance, 6) if resistance else None
        rr = None
        if stop and target and entry > stop:
            risk = entry - stop
            reward = target - entry
            if risk > 0 and reward > 0:
                rr = round(reward / risk, 2)

    return {
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "target_t1": target,
        "risk_reward_t1": rr,
        "confidence": _confidence(score_info["total"]),
    }


def format_trader_summary_table(ranked: list[dict[str, Any]]) -> str:
    """Markdown table for top of report."""
    lines = [
        "### Trader Summary (Binance — scored & ranked)",
        "",
        "| Rank | Symbol | Direction | Entry | Stop | Target (T1) | R:R | Score | Confidence |",
        "|------|--------|-----------|-------|------|-------------|-----|-------|------------|",
    ]
    for i, row in enumerate(ranked, 1):
        lv = row.get("levels") or {}
        rr = lv.get("risk_reward_t1")
        rr_s = f"{rr:.2f}:1" if rr is not None else "n/a"
        lines.append(
            f"| {i} | {row.get('base', '')} | {lv.get('direction', '')} | "
            f"${lv.get('entry', 'n/a')} | ${lv.get('stop', 'n/a')} | ${lv.get('target_t1', 'n/a')} | "
            f"{rr_s} | {row.get('score', {}).get('total', 'n/a')} | {lv.get('confidence', '')} |"
        )
    lines.append("")
    lines.append(
        "*Score 0–100 from trend, RSI, MACD, MA stack, and 24h volume vs 20-day average. "
        "Volume uses Binance 24h ticker (not partial daily candle).*"
    )
    lines.append("")
    return "\n".join(lines)


async def build_market_snapshot(
    *,
    max_coins: int = 5,
    pool_size: int | None = None,
    coin_hint: str | None = None,
) -> dict[str, Any]:
    """Fetch top coins, apply tradability filter, score, rank, and build trade levels."""
    pool = pool_size or TOP_POOL_SIZE
    top = await get_top_symbols(limit=pool)

    if coin_hint:
        sym = coin_hint.upper()
        if not sym.endswith("USDT"):
            sym = f"{sym}USDT"
        matching = [t for t in top if t["symbol"] == sym]
        if matching:
            top = matching
        else:
            t = await get_24hr(sym)
            top = [
                {
                    "symbol": sym,
                    "base": sym.replace("USDT", ""),
                    "last_price": t["last_price"],
                    "price_change_pct_24h": t["price_change_pct_24h"],
                    "quote_volume_24h": t["quote_volume_24h"],
                    "high_24h": t["high_24h"],
                    "low_24h": t["low_24h"],
                    "trade_count_24h": t["trade_count_24h"],
                }
            ]

    screened: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    async def _process(coin: dict[str, Any]) -> None:
        symbol = coin["symbol"]
        try:
            bundle = await get_price_signals_bundle(symbol)
        except Exception as e:  # noqa: BLE001
            excluded.append({**coin, "excluded_reason": str(e)})
            return

        ok, reason = passes_tradability(coin, bundle)
        score_info = compute_signal_score(bundle)
        bundle["score"] = score_info

        row = {
            **coin,
            "bundle": bundle,
            "score": score_info,
            "tradable": ok,
            "excluded_reason": reason,
        }

        if ok:
            row["levels"] = compute_trade_levels(bundle, score_info)
            screened.append(row)
        else:
            excluded.append(row)

    await asyncio.gather(*[_process(c) for c in top])

    screened.sort(key=lambda r: r["score"]["total"], reverse=True)
    ranked = screened[:max_coins]

    return {
        "pool_size": len(top),
        "tradable_count": len(screened),
        "excluded": excluded,
        "ranked_signals": ranked,
        "top_coins_all": top,
        "filters": {
            "min_quote_volume_24h": MIN_QUOTE_VOLUME_24H,
            "min_kline_bars": MIN_KLINE_BARS,
        },
    }


def snapshot_to_context(snapshot: dict[str, Any]) -> str:
    """Compact context string for the research loop."""
    lines = [
        "AUTHORITATIVE BINANCE MARKET SNAPSHOT (pre-computed — use these numbers):",
        f"Filters: min 24h quote vol ${snapshot['filters']['min_quote_volume_24h']:,.0f}, "
        f"min {snapshot['filters']['min_kline_bars']} daily bars.",
        "",
        "RANKED TRADE CANDIDATES (by signal score):",
    ]
    for i, row in enumerate(snapshot["ranked_signals"], 1):
        b = row["bundle"]
        tf1d = b["timeframes"]["1d"]
        tf4h = b["timeframes"]["4h"]
        lv = row["levels"]
        lines.append(
            f"{i}. {row['base']} score={row['score']['total']} ({row['score']['label']}) "
            f"dir={lv['direction']} entry=${lv['entry']} stop=${lv['stop']} t1=${lv['target_t1']} "
            f"rr={lv.get('risk_reward_t1')} vol24h_ratio={b.get('volume_24h_vs_avg_ratio')} "
            f"price=${b['ticker_24h']['last_price']} chg24h={b['ticker_24h']['price_change_pct_24h']}% "
            f"RSI1d={tf1d.get('rsi14')} RSI4h={tf4h.get('rsi14')} "
            f"trend1d={tf1d.get('trend')} trend4h={tf4h.get('trend')}"
        )

    if snapshot["excluded"]:
        lines.append("")
        lines.append("EXCLUDED (tradability filter):")
        for ex in snapshot["excluded"][:8]:
            lines.append(f"- {ex.get('base', ex.get('symbol'))}: {ex.get('excluded_reason')}")

    return "\n".join(lines)


def snapshot_to_json(snapshot: dict[str, Any], dt_info: dict[str, str], max_coins: int) -> dict[str, Any]:
    """Structured JSON sidecar from deterministic snapshot."""
    ranked = snapshot["ranked_signals"]
    return {
        "metadata": {
            "research_datetime": dt_info.get("datetime", ""),
            "timezone": dt_info.get("timezone", "UTC"),
            "research_date": dt_info.get("date") or "",
            "max_coins_requested": max_coins,
            "total_coins_screened": snapshot["pool_size"],
            "total_tradable": snapshot["tradable_count"],
            "total_trade_signals": len(ranked),
            "scoring": "deterministic_binance_v1",
            "filters": snapshot["filters"],
        },
        "trader_summary": [
            {
                "rank": i,
                "symbol": r["base"],
                "direction": r["levels"]["direction"],
                "entry": r["levels"]["entry"],
                "stop": r["levels"]["stop"],
                "target_t1": r["levels"]["target_t1"],
                "risk_reward_t1": r["levels"].get("risk_reward_t1"),
                "score": r["score"]["total"],
                "score_breakdown": r["score"]["breakdown"],
                "confidence": r["levels"]["confidence"],
                "last_price": r["bundle"]["ticker_24h"]["last_price"],
                "volume_24h_vs_avg_ratio": r["bundle"].get("volume_24h_vs_avg_ratio"),
            }
            for i, r in enumerate(ranked, 1)
        ],
        "top_coins_today": [
            {
                "rank": i,
                "symbol": c["base"],
                "quote_volume_24h": c["quote_volume_24h"],
                "price_change_pct_24h": c["price_change_pct_24h"],
                "tradable": any(r["symbol"] == c["symbol"] for r in ranked),
            }
            for i, c in enumerate(snapshot["top_coins_all"][:15], 1)
        ],
        "excluded": [
            {"symbol": e.get("base"), "reason": e.get("excluded_reason")}
            for e in snapshot["excluded"][:15]
        ],
        "price_signals": _price_signals_json(ranked),
        "top_trade_signals": _top_trade_signals_json(ranked),
    }


def _price_signals_json(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in ranked:
        b = row["bundle"]
        tf1d = b["timeframes"]["1d"]
        tf4h = b["timeframes"]["4h"]
        out.append(
            {
                "symbol": row["base"],
                "score": row["score"]["total"],
                "trend_1d": tf1d.get("trend"),
                "trend_4h": tf4h.get("trend"),
                "rsi_1d": tf1d.get("rsi14"),
                "rsi_4h": tf4h.get("rsi14"),
                "macd_hist_1d": (tf1d.get("macd") or {}).get("histogram"),
                "macd_hist_4h": (tf4h.get("macd") or {}).get("histogram"),
                "support_4h": tf4h.get("support"),
                "resistance_4h": tf4h.get("resistance"),
                "volume_24h_vs_avg_ratio": b.get("volume_24h_vs_avg_ratio"),
                "last_price": b["ticker_24h"]["last_price"],
            }
        )
    return out


def _top_trade_signals_json(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": i,
            "symbol": r["base"],
            "direction": r["levels"]["direction"],
            "entry": r["levels"]["entry"],
            "stop": r["levels"]["stop"],
            "target_t1": r["levels"]["target_t1"],
            "risk_reward_t1": r["levels"].get("risk_reward_t1"),
            "score": r["score"]["total"],
            "confidence": r["levels"]["confidence"],
        }
        for i, r in enumerate(ranked, 1)
    ]


def inject_trader_summary(report: str, summary_table: str) -> str:
    """Insert trader summary immediately after ## Report heading."""
    marker = "## Report"
    if marker not in report:
        return summary_table + "\n\n" + report
    idx = report.index(marker) + len(marker)
    return report[:idx] + "\n\n" + summary_table + report[idx:]


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "n/a"
    if v >= 1000:
        return f"${v:,.2f}"
    if v >= 1:
        return f"${v:.2f}"
    return f"${v:.6f}"


def _fmt_rr(rr: float | None) -> str:
    return f"{rr:.2f}:1" if rr is not None else "n/a"


def format_top_coins_table(snapshot: dict[str, Any]) -> str:
    ranked_syms = {r["symbol"] for r in snapshot["ranked_signals"]}
    lines = [
        "### Top Coins Today",
        "",
        "| Vol Rank | Symbol | 24h Change | 24h Quote Vol | Tradability |",
        "|----------|--------|------------|---------------|-------------|",
    ]
    for i, c in enumerate(snapshot["top_coins_all"][:15], 1):
        tradable = "PASS" if c["symbol"] in ranked_syms else "FAIL"
        vol = c.get("quote_volume_24h") or 0
        chg = c.get("price_change_pct_24h", 0)
        lines.append(
            f"| {i} | {c['base']} | {chg:+.2f}% | ${vol:,.0f} | {tradable} |"
        )
    lines.append("")
    return "\n".join(lines)


def format_tradability_screen(snapshot: dict[str, Any]) -> str:
    f = snapshot["filters"]
    lines = [
        "### Tradability Screen",
        "",
        f"Hard filter: min 24h quote volume **${f['min_quote_volume_24h']:,.0f}**, "
        f"min **{f['min_kline_bars']}** daily kline bars, exclude stables/leveraged tokens.",
        "",
        f"**Passed:** {snapshot['tradable_count']} coins — top {len(snapshot['ranked_signals'])} ranked below.",
        "",
    ]
    if snapshot["excluded"]:
        lines.append("**Excluded (sample):**")
        for ex in snapshot["excluded"][:10]:
            lines.append(f"- **{ex.get('base', ex.get('symbol'))}:** {ex.get('excluded_reason')}")
        lines.append("")
    return "\n".join(lines)


def format_price_signal_analysis(
    snapshot: dict[str, Any],
    catalysts: dict[str, str] | None = None,
) -> str:
    """Template Price Signal Analysis from snapshot; optional LLM catalyst text per symbol."""
    catalysts = catalysts or {}
    lines = ["### Price Signal Analysis", ""]
    for i, row in enumerate(snapshot["ranked_signals"], 1):
        base = row["base"]
        b = row["bundle"]
        tf1d = b["timeframes"]["1d"]
        tf4h = b["timeframes"]["4h"]
        lv = row["levels"]
        macd_1d = (tf1d.get("macd") or {}).get("histogram")
        macd_4h = (tf4h.get("macd") or {}).get("histogram")
        vol_ratio = b.get("volume_24h_vs_avg_ratio")

        lines.extend(
            [
                f"#### {i}. {base} — Score **{row['score']['total']}** ({row['score']['label']})",
                "",
                f"- **Trend:** 1d {tf1d.get('trend')} · 4h {tf4h.get('trend')}",
                f"- **Price:** {_fmt_price(b['ticker_24h']['last_price'])} "
                f"({b['ticker_24h']['price_change_pct_24h']:+.2f}% 24h)",
                f"- **RSI(14):** 1d {tf1d.get('rsi14')} · 4h {tf4h.get('rsi14')}",
                f"- **MACD hist:** 1d {macd_1d} · 4h {macd_4h}",
                f"- **SMAs (1d):** SMA20 {_fmt_price(tf1d.get('sma20'))} · "
                f"SMA50 {_fmt_price(tf1d.get('sma50'))} · SMA200 {_fmt_price(tf1d.get('sma200'))}",
                f"- **Support / Resistance (4h):** {_fmt_price(tf4h.get('support'))} / "
                f"{_fmt_price(tf4h.get('resistance'))}",
                f"- **Volume:** 24h/20d avg ratio **{vol_ratio}×** "
                f"(24h quote vol ${b.get('volume_24h_quote', 0):,.0f})",
                f"- **Setup:** {lv['direction']} · entry {_fmt_price(lv['entry'])} · "
                f"stop {_fmt_price(lv['stop'])} · T1 {_fmt_price(lv['target_t1'])} · "
                f"R:R {_fmt_rr(lv.get('risk_reward_t1'))}",
                "",
            ]
        )
        cat = catalysts.get(base) or catalysts.get(base.upper())
        if cat:
            lines.append(f"- **Catalysts & context:**")
            lines.append(cat.strip())
        else:
            lines.append("- **Catalysts & context:** _No catalyst narrative returned by research loop._")
        lines.append("")
    return "\n".join(lines)


def format_top_trade_signals(snapshot: dict[str, Any]) -> str:
    lines = [
        "### Top Trade Signals for the Day",
        "",
        "_Ranked by deterministic signal score. Not financial advice._",
        "",
    ]
    for i, row in enumerate(snapshot["ranked_signals"], 1):
        lv = row["levels"]
        b = row["bundle"]
        tf1d = b["timeframes"]["1d"]
        tf4h = b["timeframes"]["4h"]
        thesis = (
            f"Score {row['score']['total']}/100 — 1d {tf1d.get('trend')}, 4h {tf4h.get('trend')}, "
            f"vol {b.get('volume_24h_vs_avg_ratio')}× avg."
        )
        lines.extend(
            [
                f"#### {i}. {row['base']} — {lv['direction'].upper()} ({lv['confidence']} confidence)",
                f"- **Thesis:** {thesis}",
                f"- **Entry:** {_fmt_price(lv['entry'])} · **Stop:** {_fmt_price(lv['stop'])} · "
                f"**Target (T1):** {_fmt_price(lv['target_t1'])} · **R:R:** {_fmt_rr(lv.get('risk_reward_t1'))}",
                "",
            ]
        )
    return "\n".join(lines)


def format_risk_section(dt_info: dict[str, str]) -> str:
    ts = dt_info.get("datetime") or dt_info.get("date") or "snapshot time"
    return (
        "### Risk & Limitations\n\n"
        f"- Technical levels and scores frozen at research datetime **{ts}** ({dt_info.get('timezone', 'UTC')}).\n"
        "- Price Signal Analysis and trade levels are **template-generated from Binance**; catalyst text is from web research.\n"
        "- Low volume regimes weaken signal reliability; confirm with live order book before trading.\n"
        "- **Not financial advice.** Research summary only.\n"
    )


def parse_llm_narrative(text: str) -> dict[str, Any]:
    """Extract Executive Summary and per-coin catalyst blocks from LLM output."""
    result: dict[str, Any] = {
        "executive_summary": "",
        "catalysts": {},
        "references": "",
    }
    if not text or not text.strip():
        return result

    # Strip JSON blocks if model still emits them
    text = re.sub(r"## JSON Output[\s\S]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```json[\s\S]*?```", "", text)

    exec_match = re.search(
        r"### Executive Summary\s*\n([\s\S]*?)(?=\n### Catalysts|\n### References|\Z)",
        text,
        re.IGNORECASE,
    )
    if exec_match:
        result["executive_summary"] = exec_match.group(1).strip()

    ref_match = re.search(r"### References\s*\n([\s\S]*?)(?=\n## |\Z)", text, re.IGNORECASE)
    if ref_match:
        result["references"] = ref_match.group(1).strip()

    cat_section = re.search(
        r"### Catalysts\s*\n([\s\S]*?)(?=\n### References|\n### Executive|\Z)",
        text,
        re.IGNORECASE,
    )
    if cat_section:
        body = cat_section.group(1).strip()
        for sym, content in re.findall(
            r"####\s+([A-Z0-9]{2,12})\s*\n([\s\S]*?)(?=\n####\s+[A-Z0-9]{2,12}\s*\n|\Z)",
            body,
            flags=re.IGNORECASE,
        ):
            result["catalysts"][sym.upper()] = content.strip()

    # Fallback: whole narrative as executive summary if structured parse failed
    if not result["executive_summary"] and not result["catalysts"]:
        cleaned = text.strip()
        if cleaned.startswith("## Narrative"):
            cleaned = re.sub(r"^## Narrative\s*", "", cleaned).strip()
        result["executive_summary"] = cleaned[:8000]

    return result


def assemble_report(
    snapshot: dict[str, Any],
    summary_table: str,
    llm_narrative: dict[str, Any],
    dt_info: dict[str, str],
) -> str:
    """Merge deterministic Binance sections with LLM executive summary + catalysts."""
    research_date = dt_info.get("date") or (dt_info.get("datetime") or "")[:10] or "today"
    parts = [
        f"# Trade Signal Briefing — {research_date}",
        "",
        "## Report",
        "",
        summary_table,
        "",
        "### Executive Summary",
        "",
        llm_narrative.get("executive_summary") or "_Executive summary not generated._",
        "",
        format_top_coins_table(snapshot),
        format_tradability_screen(snapshot),
        format_price_signal_analysis(snapshot, llm_narrative.get("catalysts")),
        format_top_trade_signals(snapshot),
        format_risk_section(dt_info),
    ]
    refs = llm_narrative.get("references")
    if refs:
        parts.extend(["", "### References", "", refs])
    return "\n".join(parts)
