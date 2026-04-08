"""
India legal article discovery via Bright Data SERP.

Flow: run **all court tiers** in `COURT_TIERS` (Supreme Court, High Court, NCLT, etc.) → **direct**
SERP queries aimed at **currently running / listed / pending** matters (cause lists, board
listings, ongoing hearings) for the given calendar context → compile distinct article topics
from snippets → queue + article writing.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .agents.baseclass import ResearchAgent, ResearchRunner
from .agents.utils.parse_output import create_type_parser
from .llm_config import LLMConfig, create_default_config, model_supports_structured_output
from .tools.brightdata_tools import brightdata_search


# Substantive taxonomy for DiscoveredTopic.branch (compiler infers from story content)
LAW_BRANCHES: tuple[str, ...] = (
    "constitutional",
    "criminal",
    "civil",
    "taxation",
    "corporate",
    "labour",
    "administrative",
    "environmental",
    "intellectual_property",
    "family",
    "banking_securities",
    "insolvency",
    "competition",
    "consumer",
    "real_estate",
    "arbitration",
    "cyber",
    "other",
)

# Discovery targets: every tier is queried each run (within `max_discovery_searches` budget)
COURT_TIERS: tuple[str, ...] = (
    "supreme_court",
    "high_court",
    "district_court",
    "sessions_court",
    "family_court",
    "consumer_commission",
    "nclt_nclat",
    "itat",
    "cat",
    "ngt",
    "drt",
    "cci",
    "armed_forces_tribunal",
    "other_tribunal",
)


class DiscoveredTopic(BaseModel):
    title: str
    provisional_angle: str = Field(description="Editorial line in one sentence")
    branch: str = Field(
        description="Legal branch id, one of: " + ", ".join(LAW_BRANCHES),
    )
    priority: str = Field(default="medium", description="high | medium | low")
    seed_phrases: List[str] = Field(
        default_factory=list,
        description="Short phrases to use in downstream research (parties, courts, statutes)",
    )


class TopicCompilation(BaseModel):
    topics: List[DiscoveredTopic] = Field(max_length=15)


def _parse_run_date(run_date: str) -> str:
    """Validate YYYY-MM-DD and return normalized string."""
    datetime.strptime(run_date, "%Y-%m-%d")
    return run_date


def _norm_query_key(q: str) -> str:
    return re.sub(r"\s+", " ", (q or "").lower().strip())[:500]


def _court_tier_label(tier: str) -> str:
    """Short human label for query strings."""
    return {
        "supreme_court": "Supreme Court of India",
        "high_court": "High Court India",
        "district_court": "district court India",
        "sessions_court": "sessions court India",
        "family_court": "family court India",
        "consumer_commission": "consumer commission India NCDRC state commission",
        "nclt_nclat": "NCLT NCLAT",
        "itat": "ITAT Income Tax Appellate Tribunal India",
        "cat": "Central Administrative Tribunal CAT India",
        "ngt": "National Green Tribunal NGT India",
        "drt": "Debt Recovery Tribunal DRT India",
        "cci": "Competition Commission of India CCI",
        "armed_forces_tribunal": "Armed Forces Tribunal India",
        "other_tribunal": "India tribunal ongoing matters",
    }.get(tier, "India court")


# Query templates per tier: {rd} = run_date YYYY-MM-DD, {my} = "Month YYYY", {lab} = tier label phrase
_COURT_TIER_QUERY_TEMPLATES: dict[str, list[str]] = {
    "supreme_court": [
        "{lab} listed matters cause list pending cases {rd}",
        "{lab} ongoing hearings matters listed {my}",
        "site:livelaw.in Supreme Court listed bench matters India {my}",
        "site:barandbench.com Supreme Court India cause list ongoing {rd}",
        "site:sci.gov.in Supreme Court cause list listed matter",
        "{lab} Constitution bench matters listed pending {my}",
    ],
    "high_court": [
        "{lab} cause list ongoing cases listed matters {my}",
        "{lab} pending matters listed hearings {rd}",
        "site:livelaw.in High Court cause list India ongoing {my}",
        "site:barandbench.com High Court listed matters pending India {rd}",
        "High Court India daily board ongoing cases {my}",
    ],
    "district_court": [
        "{lab} cause list ongoing trials listed {my}",
        "district court India pending cases listed matters {rd}",
        "site:livelaw.in district court cause list India {my}",
    ],
    "sessions_court": [
        "{lab} ongoing trials pending matters {my}",
        "sessions court India listed cases hearings {rd}",
        "site:livelaw.in sessions court India ongoing {my}",
    ],
    "family_court": [
        "{lab} pending matters listed hearings {my}",
        "family court India ongoing matrimonial cases {rd}",
        "site:livelaw.in family court India listed {my}",
    ],
    "consumer_commission": [
        "{lab} ongoing hearings pending complaints {my}",
        "NCDRC state consumer commission listed matters India {rd}",
        "site:livelaw.in consumer commission India pending {my}",
    ],
    "nclt_nclat": [
        "{lab} listed matters ongoing hearings cause list {my}",
        "NCLT NCLAT India pending matters listed {rd}",
        "site:livelaw.in NCLT listed matters ongoing {my}",
        "site:barandbench.com NCLAT matters listed India {my}",
    ],
    "itat": [
        "{lab} cause list listed matters ongoing {my}",
        "ITAT India pending appeals listed hearings {rd}",
        "site:livelaw.in ITAT listed matters India {my}",
    ],
    "cat": [
        "{lab} listed matters ongoing hearings {my}",
        "CAT Central Administrative Tribunal India pending listed {rd}",
        "site:livelaw.in CAT tribunal India listed {my}",
    ],
    "ngt": [
        "{lab} listed matters ongoing hearings cause list {my}",
        "NGT National Green Tribunal India pending matters {rd}",
        "site:livelaw.in NGT listed matters India {my}",
    ],
    "drt": [
        "{lab} ongoing matters listed hearings {my}",
        "Debt Recovery Tribunal India pending cases listed {rd}",
    ],
    "cci": [
        "{lab} ongoing proceedings hearings listed {my}",
        "Competition Commission of India CCI pending matters hearing {rd}",
        "site:livelaw.in CCI India proceedings ongoing {my}",
    ],
    "armed_forces_tribunal": [
        "{lab} listed matters ongoing hearings {my}",
        "Armed Forces Tribunal India pending cases listed {rd}",
    ],
    "other_tribunal": [
        "{lab} tribunal India listed matters ongoing {my}",
        "India tribunal cause list pending hearings {rd}",
        "site:livelaw.in tribunal India listed ongoing {my}",
    ],
}


def _build_running_case_queries(run_date: str, tier: str) -> List[str]:
    """
    SERP queries aimed at **currently running / listed / pending** matters for the court tier.
    """
    run_date = _parse_run_date(run_date)
    dt = datetime.strptime(run_date, "%Y-%m-%d")
    month_year = dt.strftime("%B %Y")
    lab = _court_tier_label(tier)
    templates = _COURT_TIER_QUERY_TEMPLATES.get(tier) or _COURT_TIER_QUERY_TEMPLATES["other_tribunal"]
    queries = [t.format(rd=run_date, my=month_year, lab=lab) for t in templates]
    seen: set[str] = set()
    out: List[str] = []
    for q in queries:
        k = _norm_query_key(q)
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out


def _init_compiler_agent(config: LLMConfig) -> ResearchAgent:
    _branch_line = " | ".join(LAW_BRANCHES)
    instructions = f"""
You turn raw Google / legal-news search snippets into distinct analytical article topics about INDIA.

Context:
- Discovery targeted **currently running, listed, pending, or cause-list** matters across **multiple court tiers**
  (see digest: each SERP block is tagged with its tier id, e.g. supreme_court, high_court, NCLT). Snippets may mention boards, listings, next dates, ongoing hearings, or pending cases.
- Each topic should describe a **concrete live or recently listed matter** where the snippet supports it—not generic "law overview" pieces.

Rules:
- Each topic must read like a plausible legal news desk or analytical article (not a press release).
- Prefer topics tied to **active litigation or tribunal proceedings** (listed, adjourned, reserved, ongoing trial, interim order) when snippets allow.
- Deduplicate overlapping stories.
- Set "branch" from the **substantive** area of the dispute (constitutional, criminal, civil, taxation, corporate, labour,
  administrative, environmental, intellectual_property, family, banking_securities, insolvency, competition, consumer,
  real_estate, arbitration, cyber, other)—infer from snippet content; do not copy the court tier id as branch.
  Valid branch ids (use exactly one per topic): {_branch_line}
- seed_phrases: 3–8 short phrases (court/tribunal name, case type, parties or statute if visible).

CRITICAL: Output ONE JSON object: {{"topics": [<objects>]}}. Each topic object must have:
"title", "provisional_angle", "branch", "priority" (high|medium|low), "seed_phrases" (array of strings).
Do NOT output JSON Schema, $defs, "properties", or merge schema with data.

Example (abbreviated):
{{"topics": [{{"title": "Example listed matter", "provisional_angle": "Why the ongoing proceeding matters", "branch": "civil", "priority": "high", "seed_phrases": ["High Court", "WP", "interim relief"]}}]}}
"""
    selected = config.main_model

    def _compile_fallback(_raw: str) -> TopicCompilation:
        return TopicCompilation(
            topics=[
                DiscoveredTopic(
                    title="India court developments (manual review needed)",
                    provisional_angle="Topic compilation failed; review SERP digest.",
                    branch="other",
                    priority="low",
                    seed_phrases=["India", "court", "listed matter"],
                )
            ]
        )

    return ResearchAgent(
        name="IndiaLegalTopicCompiler",
        instructions=instructions,
        model=selected,
        output_type=TopicCompilation if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(
            TopicCompilation,
            fallback_on_validation_error=_compile_fallback,
        )
        if not model_supports_structured_output(selected)
        else None,
    )


def _plan_tier_queries(
    run_date: str,
    *,
    max_total: int,
) -> List[tuple[str, str]]:
    """
    Build (court_tier_id, query) pairs covering every tier at least once (when max_total allows),
    then round-robin remaining budget with global query deduplication.
    """
    run_date = _parse_run_date(run_date)
    max_total = max(1, max_total)
    by_tier: dict[str, List[str]] = {
        tier: _build_running_case_queries(run_date, tier) for tier in COURT_TIERS
    }
    seen_keys: set[str] = set()
    out: List[tuple[str, str]] = []

    # Phase 1: one distinct query per tier (preserves COURT_TIERS order)
    for tier in COURT_TIERS:
        if len(out) >= max_total:
            break
        for q in by_tier[tier]:
            k = _norm_query_key(q)
            if k not in seen_keys:
                seen_keys.add(k)
                out.append((tier, q))
                break

    # Phase 2: round-robin further queries until cap or exhaustion
    idx: dict[str, int] = {t: 0 for t in COURT_TIERS}
    for t in COURT_TIERS:
        # advance index past queries already taken in phase 1 for this tier
        qs = by_tier[t]
        while idx[t] < len(qs) and _norm_query_key(qs[idx[t]]) in seen_keys:
            idx[t] += 1

    while len(out) < max_total:
        added = False
        for tier in COURT_TIERS:
            if len(out) >= max_total:
                break
            qs = by_tier[tier]
            i = idx[tier]
            while i < len(qs):
                q = qs[i]
                i += 1
                k = _norm_query_key(q)
                if k not in seen_keys:
                    seen_keys.add(k)
                    out.append((tier, q))
                    idx[tier] = i
                    added = True
                    break
            idx[tier] = i
        if not added:
            break

    return out


def _format_serp_digest(
    run_date: str,
    court_tiers_summary: str,
    results_per_query: List[tuple[str, str, List[dict]]],
) -> str:
    lines: List[str] = [
        f"RUN_DATE: {run_date}",
        f"COURT_TIERS_COVERED: {court_tiers_summary}",
        "",
        "=== SERP RESULTS (running / listed / pending matters; COURT_TIER per block) ===",
        "",
    ]
    for tier, q, rows in results_per_query:
        lines.append(f"COURT_TIER: {tier}")
        lines.append(f"QUERY: {q}")
        for r in rows[:6]:
            if not isinstance(r, dict) or r.get("error"):
                lines.append(f"  ERROR: {r.get('error', r)}")
                continue
            url = r.get("url", "")
            title = r.get("title", "")
            desc = (r.get("description") or r.get("text") or "")[:1200]
            lines.append(f"  - {title}\n    {url}\n    {desc[:500]}")
        lines.append("")
    return "\n".join(lines)


async def _search_queries(
    queries: List[str],
    *,
    max_concurrent: int = 3,
) -> List[tuple[str, List[dict]]]:
    sem = asyncio.Semaphore(max_concurrent)

    async def one(q: str) -> tuple[str, List[dict]]:
        async with sem:
            print(f"\n[DISCOVERY] SERP query: {q}", flush=True)
            raw = await brightdata_search(q, max_results=5, include_ai_overview=True)
            return q, raw if raw else []

    return list(await asyncio.gather(*[one(q) for q in queries]))


async def compile_topics_from_serp(
    run_date: str,
    serp_digest: str,
    config: Optional[LLMConfig] = None,
    *,
    court_tiers_summary: str = "",
) -> TopicCompilation:
    _parse_run_date(run_date)
    config = config or create_default_config()
    agent = _init_compiler_agent(config)
    tier_line = (
        f"\nCOURT_TIERS (SERP discovery targets): {court_tiers_summary}\n"
        if court_tiers_summary
        else ""
    )
    result = await ResearchRunner.run(
        agent,
        f"RUN_DATE: {run_date}{tier_line}\nRAW_SNIPPETS_AND_RESULTS:\n{serp_digest[:80000]}",
    )
    return result.final_output_as(TopicCompilation)


async def discover_topics_for_date(
    run_date: str,
    config: Optional[LLMConfig] = None,
    *,
    max_concurrent_searches: int = 2,
    max_discovery_searches: int = 18,
) -> TopicCompilation:
    """
    All court tiers (within budget) → SERP for **running / listed / pending** matters → compile topics.
    """
    _parse_run_date(run_date)
    config = config or create_default_config()

    planned = _plan_tier_queries(run_date, max_total=max(1, max_discovery_searches))
    tiers_in_run = sorted({t for t, _ in planned})
    print(
        f"\n[DISCOVERY] Court tiers this run ({len(tiers_in_run)}/{len(COURT_TIERS)}): "
        f"{', '.join(tiers_in_run)}",
        flush=True,
    )
    if len(tiers_in_run) < len(COURT_TIERS):
        print(
            f"[DISCOVERY] Note: SERP budget ({max_discovery_searches}) is below the number of "
            f"court tiers ({len(COURT_TIERS)}); not every tier is queried. Use "
            f"--max-discovery-searches >= {len(COURT_TIERS)} to cover each tier at least once.",
            flush=True,
        )
    print(f"[DISCOVERY] Planned SERP calls: {len(planned)}", flush=True)

    queries_in_order = [q for _, q in planned]
    pairs_flat = await _search_queries(queries_in_order, max_concurrent=max_concurrent_searches)
    # Re-attach tier labels (order matches planned)
    pairs: List[tuple[str, str, List[dict]]] = [
        (planned[i][0], pairs_flat[i][0], pairs_flat[i][1]) for i in range(len(planned))
    ]
    summary = f"{len(tiers_in_run)} tiers; ids: {', '.join(COURT_TIERS)}"
    digest = _format_serp_digest(run_date, summary, pairs)
    print(
        f"\n[DISCOVERY] Running-matters discovery finished: {len(pairs)} SERP call(s).",
        flush=True,
    )
    return await compile_topics_from_serp(
        run_date,
        digest,
        config=config,
        court_tiers_summary=summary,
    )


def topic_title_key(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s[:200]
