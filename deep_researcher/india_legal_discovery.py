"""
India legal article discovery via Bright Data SERP.

Default: **chained discovery** — the model proposes one seed query, we run SERP, the model reads
snippets and proposes the next 0–2 queries, repeat until it stops or limits hit, then compile
topics from the accumulated digest.

Optional **legacy batch**: plan many queries upfront, run in parallel (old behaviour).
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .agents.baseclass import ResearchAgent, ResearchRunner
from .agents.utils.parse_output import create_type_parser
from .llm_config import LLMConfig, create_default_config, model_supports_structured_output
from .tools.brightdata_tools import brightdata_search


class IndirectSearchPlan(BaseModel):
    """Legacy batch planner: many queries at once."""

    queries: List[str] = Field(
        min_length=3,
        max_length=12,
        description="6–14 words each; India-implied; institution / place / sector / public body angles",
    )
    planner_notes: str = Field(default="", description="Internal rationale (not shown to readers)")


class SeedSearchOutput(BaseModel):
    """Single opening SERP query for chained discovery."""

    query: str = Field(description="6–14 words, India-implied, indirect, one search string")
    angle_brief: str = Field(default="", description="Why this angle (internal)")


class ChainedSearchDecision(BaseModel):
    """After each SERP round: continue with follow-up queries or stop."""

    next_queries: List[str] = Field(
        default_factory=list,
        description="0–2 new Google queries using entities/themes from results; empty if stopping",
    )
    stop_discovery: bool = Field(
        default=False,
        description="True when snippets already cover enough diverse threads for many daily articles",
    )
    rolling_notes: str = Field(
        default="",
        description="Short memo of themes/entities seen (optional; helps next step)",
    )

    @field_validator("next_queries", mode="before")
    @classmethod
    def _cap_queries(cls, v: object) -> List[str]:
        if not isinstance(v, list):
            return []
        out = [str(x).strip() for x in v if str(x).strip()]
        return out[:2]


class DiscoveredTopic(BaseModel):
    title: str
    provisional_angle: str = Field(description="Editorial line in one sentence")
    branch: str = Field(
        description="constitutional | criminal | civil | taxation | corporate | labour | administrative | other"
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


def _init_planner_agent(config: LLMConfig) -> ResearchAgent:
    instructions = """
You plan INDIRECT Google search queries to surface India-relevant stories that may have legal
dimensions (courts, regulators, investigations, federalism, elections, taxation, insolvency,
crime, environment, labour). The user states RUN_DATE (YYYY-MM-DD).

STRICT RULES:
- Do NOT use queries like "legal news India", "latest judgments", "Supreme Court today", or
  bare "case law".
- DO use: institution + event, city + public body, sector + regulator, named lecture or report,
  ongoing dispute themes, policy implementation friction, enforcement agency + sector, tribunal + company type.
- Every query must be plausibly about India (include "India", a state/city, or site:livelaw.in / site:barandbench.com / site:gov.in sparingly).
- 6–14 words per query; 4–12 queries.

CRITICAL: Output ONE JSON object with fields "queries" (array of strings) and optional "planner_notes" (string).
Do NOT output JSON Schema, $defs, "properties", or schema metadata.

Example:
{"queries": ["RBI penalty cooperative banks Maharashtra governance 2026", "NGT construction waste Delhi NCR builders"], "planner_notes": ""}
"""
    selected = config.reasoning_model

    def _plan_fallback(_raw: str) -> IndirectSearchPlan:
        return IndirectSearchPlan(
            queries=[
                "India regulator enforcement sector disputes site:gov.in 2026",
                "High Court tribunal Mumbai Delhi policy litigation April 2026",
            ],
            planner_notes="Fallback: invalid planner JSON",
        )

    return ResearchAgent(
        name="IndiaLegalIndirectPlanner",
        instructions=instructions,
        model=selected,
        output_type=IndirectSearchPlan if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(
            IndirectSearchPlan,
            fallback_on_validation_error=_plan_fallback,
        )
        if not model_supports_structured_output(selected)
        else None,
    )


def _init_seed_agent(config: LLMConfig) -> ResearchAgent:
    instructions = """
You choose ONE opening Google search query for India-focused discovery (RUN_DATE given by user).

Goals:
- Be creative and varied (different sector/region/institution each time you are invoked); avoid repeating
  the same template as generic "GST + council" or "RERA + delay" unless the user context demands it.
- Indirect angle: regulator, tribunal, municipal body, sector enforcement, interstate dispute, public body,
  policy implementation friction — NOT "legal news India" or "latest Supreme Court".

Rules:
- Single string in field "query", 6–14 words, India-implied (city, India, site:gov.in, or known Indian body).
- Optional "angle_brief" one short sentence.

Output JSON only, no schema metadata:
{"query": "your search string", "angle_brief": ""}
"""
    selected = config.reasoning_model

    def _fb(_raw: str) -> SeedSearchOutput:
        return SeedSearchOutput(
            query="India electricity commission tariff dispute renewable generators 2026",
            angle_brief="fallback seed",
        )

    return ResearchAgent(
        name="IndiaLegalChainedSeed",
        instructions=instructions,
        model=selected,
        output_type=SeedSearchOutput if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(SeedSearchOutput, fallback_on_validation_error=_fb)
        if not model_supports_structured_output(selected)
        else None,
    )


def _init_chained_step_agent(config: LLMConfig) -> ResearchAgent:
    instructions = """
You drive chained Google search discovery for INDIA legal-article ideas.

You receive:
- RUN_DATE
- How many searches have already run
- Optional ROLLING_THEME_NOTES from prior steps
- FULL_DIGEST_SO_FAR (SERP titles/snippets/URLs, may be truncated at the end)
- MOST_RECENT_RESULTS_ONLY (just the last round)

Task:
1. Read MOST_RECENT_RESULTS_ONLY and FULL_DIGEST_SO_FAR. Extract concrete entities: courts, tribunals,
   regulators, statutes, cities, company/agency names, judge or report titles if present.
2. Propose **0 to 2** NEW follow-up queries that branch from what you saw (narrower court + party,
   related regulator, sibling statute, different region same issue). Each query 6–14 words, India-implied,
   still indirect (not "latest judgment" boilerplate).
3. Set stop_discovery true ONLY when there is already a wide spread of distinct story threads across
   rounds (enough to draft roughly 8–15 different analytical articles). If results were thin or repetitive,
   keep stop_discovery false and suggest sharp follow-ups.
4. Optional rolling_notes: one or two sentences summarising themes for the next call.

Output JSON only, no $defs:
{"next_queries": ["..."], "stop_discovery": false, "rolling_notes": ""}
"""
    selected = config.reasoning_model

    def _fb(_raw: str) -> ChainedSearchDecision:
        return ChainedSearchDecision(next_queries=[], stop_discovery=True, rolling_notes="fallback stop")

    return ResearchAgent(
        name="IndiaLegalChainedStep",
        instructions=instructions,
        model=selected,
        output_type=ChainedSearchDecision if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(ChainedSearchDecision, fallback_on_validation_error=_fb)
        if not model_supports_structured_output(selected)
        else None,
    )


def _init_compiler_agent(config: LLMConfig) -> ResearchAgent:
    instructions = """
You turn raw search snippets into distinct legal-article topics about INDIA.

Rules:
- Each topic must be a plausible analytical article (facts → issues → likely legal hooks), not a press release.
- Deduplicate overlapping stories.
- Map each to a branch (constitutional, criminal, civil, taxation, corporate, labour, administrative, other).
- seed_phrases: 3–8 short phrases for follow-up research (court names, statutes, parties if visible).

CRITICAL: Output ONE JSON object: {"topics": [<objects>]}. Each topic object must have:
"title", "provisional_angle", "branch", "priority" (high|medium|low), "seed_phrases" (array of strings).
Do NOT output JSON Schema, $defs, "properties", or merge schema with data.

Example (abbreviated):
{"topics": [{"title": "Example headline", "provisional_angle": "Why it matters legally", "branch": "administrative", "priority": "high", "seed_phrases": ["Statute X", "Tribunal Y"]}]}
"""
    selected = config.main_model

    def _compile_fallback(_raw: str) -> TopicCompilation:
        return TopicCompilation(
            topics=[
                DiscoveredTopic(
                    title="India legal developments (manual review needed)",
                    provisional_angle="SERP compilation failed; narrow with direct searches.",
                    branch="other",
                    priority="low",
                    seed_phrases=["India", "court", "2026"],
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


def _format_serp_digest(run_date: str, results_per_query: List[tuple[str, List[dict]]]) -> str:
    lines: List[str] = [f"RUN_DATE: {run_date}", "", "=== SERP RESULTS ===", ""]
    for q, rows in results_per_query:
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


async def discover_topics_chained(
    run_date: str,
    config: Optional[LLMConfig] = None,
    *,
    max_rounds: int = 8,
    max_searches: int = 18,
    max_concurrent: int = 2,
) -> TopicCompilation:
    """
    AI seed query → SERP → read results → next 0–2 queries → … → compile topics.
    """
    _parse_run_date(run_date)
    config = config or create_default_config()

    seed_agent = _init_seed_agent(config)
    step_agent = _init_chained_step_agent(config)

    jitter = uuid.uuid4().hex[:10]
    sres = await ResearchRunner.run(
        seed_agent,
        f"RUN_DATE: {run_date}. SESSION_JITTER: {jitter} (ignore in query text; use only so this run differs from others). "
        f"Propose the first exploratory search.",
    )
    seed = sres.final_output_as(SeedSearchOutput)
    current: List[str] = [seed.query.strip()] if seed.query.strip() else []

    if not current:
        current = ["India tribunal regulatory order sector dispute site:gov.in 2026"]

    seen: set[str] = set()
    pairs: List[tuple[str, List[dict]]] = []
    total_searches = 0
    rolling_notes: List[str] = []
    round_idx = 0

    while round_idx < max_rounds and total_searches < max_searches:
        to_run: List[str] = []
        for q in current:
            k = _norm_query_key(q)
            if k and k not in seen:
                seen.add(k)
                to_run.append(q.strip())
        if not to_run:
            break

        budget = max_searches - total_searches
        to_run = to_run[: min(len(to_run), max_concurrent, budget)]
        if not to_run:
            break

        batch = await _search_queries(to_run, max_concurrent=max_concurrent)
        pairs.extend(batch)
        total_searches += len(batch)
        last_block = _format_serp_digest(run_date, batch)
        digest_full = _format_serp_digest(run_date, pairs)

        if total_searches >= max_searches:
            break

        notes_join = " | ".join(rolling_notes[-6:])
        chain_prompt = f"""RUN_DATE: {run_date}
CHAIN_ROUND: {round_idx + 1} of up to {max_rounds}
SEARCHES_COMPLETED: {total_searches} (hard cap {max_searches})
ROLLING_THEME_NOTES: {notes_join or "(none yet)"}

FULL_DIGEST_SO_FAR (may be truncated at start; newest rounds at end):
{digest_full[-48000:]}

MOST_RECENT_RESULTS_ONLY:
{last_block}
"""
        cres = await ResearchRunner.run(step_agent, chain_prompt)
        decision = cres.final_output_as(ChainedSearchDecision)

        if decision.rolling_notes.strip():
            rolling_notes.append(decision.rolling_notes.strip()[:600])

        if decision.stop_discovery:
            print("\n[DISCOVERY] Model signaled stop_discovery (enough breadth).", flush=True)
            break

        nxt = [q.strip() for q in decision.next_queries if q.strip()][:2]
        if not nxt:
            print("\n[DISCOVERY] No follow-up queries; ending chain.", flush=True)
            break

        current = nxt
        round_idx += 1

    final_digest = _format_serp_digest(run_date, pairs)
    print(f"\n[DISCOVERY] Chained discovery finished: {total_searches} search(es), {len(pairs)} result block(s).", flush=True)
    return await compile_topics_from_serp(run_date, final_digest, config=config)


async def plan_indirect_queries(run_date: str, config: Optional[LLMConfig] = None) -> IndirectSearchPlan:
    _parse_run_date(run_date)
    config = config or create_default_config()
    agent = _init_planner_agent(config)
    prompt = f"RUN_DATE: {run_date}. Plan indirect search queries to surface India stories with potential legal angles."
    result = await ResearchRunner.run(agent, prompt)
    return result.final_output_as(IndirectSearchPlan)


async def compile_topics_from_serp(
    run_date: str,
    serp_digest: str,
    config: Optional[LLMConfig] = None,
) -> TopicCompilation:
    _parse_run_date(run_date)
    config = config or create_default_config()
    agent = _init_compiler_agent(config)
    result = await ResearchRunner.run(
        agent,
        f"RUN_DATE: {run_date}\n\nRAW_SNIPPETS_AND_RESULTS:\n{serp_digest[:80000]}",
    )
    return result.final_output_as(TopicCompilation)


async def discover_topics_for_date(
    run_date: str,
    config: Optional[LLMConfig] = None,
    *,
    legacy_batch: bool = False,
    max_concurrent_searches: int = 2,
    max_chained_rounds: int = 8,
    max_discovery_searches: int = 18,
) -> TopicCompilation:
    """
    Default: chained AI-driven discovery. Set legacy_batch=True for old plan-all-then-parallel behaviour.
    """
    if legacy_batch:
        plan = await plan_indirect_queries(run_date, config=config)
        pairs = await _search_queries(plan.queries, max_concurrent=max_concurrent_searches)
        digest = _format_serp_digest(run_date, pairs)
        return await compile_topics_from_serp(run_date, digest, config=config)

    return await discover_topics_chained(
        run_date,
        config=config,
        max_rounds=max_chained_rounds,
        max_searches=max_discovery_searches,
        max_concurrent=max_concurrent_searches,
    )


def topic_title_key(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s[:200]
