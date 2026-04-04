"""
Indirect discovery of India legal article topics: plan non-legal-looking queries, run SERP,
then compile distinct topics with source hints. Jurisdiction and tone are enforced in the
downstream iterative researcher, not in raw search strings.
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


class IndirectSearchPlan(BaseModel):
    """Indirect SERP queries — avoid explicit 'legal news' / 'latest judgment' phrasing."""

    queries: List[str] = Field(
        min_length=3,
        max_length=12,
        description="6–14 words each; India-implied; institution / place / sector / public body angles",
    )
    planner_notes: str = Field(default="", description="Internal rationale (not shown to readers)")


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


def _init_planner_agent(config: LLMConfig) -> ResearchAgent:
    instructions = f"""
You plan INDIRECT Google search queries to surface India-relevant stories that may have legal
dimensions (courts, regulators, investigations, federalism, elections, taxation, insolvency,
crime, environment, labour). Calendar focus date: the user will state RUN_DATE (YYYY-MM-DD).

STRICT RULES:
- Do NOT use queries like "legal news India", "latest judgments", "Supreme Court today", or
  bare "case law".
- DO use: institution + event, city + public body, sector + regulator, named lecture or report,
  ongoing dispute themes, policy implementation friction, enforcement agency + sector, tribunal + company type.
- Every query must be plausibly about India (include "India", a state/city, or site:livelaw.in / site:barandbench.com / site:gov.in sparingly).
- 6–14 words per query; 4–12 queries.

Output JSON only:
{IndirectSearchPlan.model_json_schema()}
"""
    selected = config.reasoning_model
    return ResearchAgent(
        name="IndiaLegalIndirectPlanner",
        instructions=instructions,
        model=selected,
        output_type=IndirectSearchPlan if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(IndirectSearchPlan)
        if not model_supports_structured_output(selected)
        else None,
    )


def _init_compiler_agent(config: LLMConfig) -> ResearchAgent:
    instructions = f"""
You turn raw search snippets into distinct legal-article topics about INDIA.

Rules:
- Each topic must be a plausible analytical article (facts → issues → likely legal hooks), not a press release.
- Deduplicate overlapping stories.
- Map each to a branch (constitutional, criminal, civil, taxation, corporate, labour, administrative, other).
- seed_phrases: 3–8 short phrases for follow-up research (court names, statutes, parties if visible).

Output JSON only:
{TopicCompilation.model_json_schema()}
"""
    selected = config.main_model
    return ResearchAgent(
        name="IndiaLegalTopicCompiler",
        instructions=instructions,
        model=selected,
        output_type=TopicCompilation if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(TopicCompilation)
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
            raw = await brightdata_search(q, max_results=5, include_ai_overview=True)
            return q, raw if raw else []

    return list(await asyncio.gather(*[one(q) for q in queries]))


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
    max_concurrent_searches: int = 3,
) -> TopicCompilation:
    """
    Full discovery: indirect query plan → Bright Data SERP → topic compilation.
    """
    plan = await plan_indirect_queries(run_date, config=config)
    pairs = await _search_queries(plan.queries, max_concurrent=max_concurrent_searches)
    digest = _format_serp_digest(run_date, pairs)
    return await compile_topics_from_serp(run_date, digest, config=config)


def topic_title_key(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s[:200]
