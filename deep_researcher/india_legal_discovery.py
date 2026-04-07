"""
India legal article discovery via Bright Data SERP.

Flow: pick a **random law branch** (criminal, civil, etc.) → run a fixed set of **direct**
legal-news queries for the given calendar date → compile distinct article topics from SERP
snippets → downstream queue + article writing uses those topics.
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .agents.baseclass import ResearchAgent, ResearchRunner
from .agents.utils.parse_output import create_type_parser
from .llm_config import LLMConfig, create_default_config, model_supports_structured_output
from .tools.brightdata_tools import brightdata_search


# Must match DiscoveredTopic.branch vocabulary (main branches of Indian / common legal taxonomy)
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


def _branch_search_label(branch: str) -> str:
    """Phrase for Google queries (not the taxonomy id)."""
    return {
        "constitutional": "constitutional law",
        "criminal": "criminal law",
        "civil": "civil law",
        "taxation": "tax law",
        "corporate": "corporate law",
        "labour": "labour law",
        "administrative": "administrative law",
        "environmental": "environmental law",
        "intellectual_property": "intellectual property law",
        "family": "family law",
        "banking_securities": "banking and securities law",
        "insolvency": "insolvency law",
        "competition": "competition law",
        "consumer": "consumer protection law",
        "real_estate": "real estate law",
        "arbitration": "arbitration law",
        "cyber": "cyber law",
        "other": "India legal",
    }.get(branch, "India legal")


def _build_direct_queries(run_date: str, branch: str) -> List[str]:
    """
    Direct legal-news SERP queries: India + branch + date/month, plus major legal news sites.
    No indirect / regulator-only angles.
    """
    run_date = _parse_run_date(run_date)
    dt = datetime.strptime(run_date, "%Y-%m-%d")
    month_year = dt.strftime("%B %Y")
    label = _branch_search_label(branch)
    queries: List[str] = [
        f"India {label} legal news {run_date}",
        f"India {label} court news {month_year}",
        f"site:barandbench.com India {label} {run_date}",
        f"site:livelaw.in {label} India {month_year}",
        f"India {label} Supreme Court High Court news {run_date}",
        f"India legal news {label} {month_year}",
        f"India {label} litigation judgment news {run_date}",
        f"India {label} tribunal court news {month_year}",
    ]
    # Dedupe while preserving order
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
- Discovery used DIRECT legal-news searches for the given RUN_DATE and a SELECTED LAW BRANCH (e.g. criminal).
- Stories should be grounded in what appears in the snippets (headlines, URLs, descriptions).

Rules:
- Each topic must read like a plausible legal news desk or analytical article (not a press release).
- Prefer topics clearly tied to the RUN_DATE or the reporting period in the results.
- Deduplicate overlapping stories.
- Set "branch" to the SELECTED_BRANCH when the story fits that area; otherwise infer from content.
  Valid branch ids (use exactly one per topic): {_branch_line}
- seed_phrases: 3–8 short phrases for follow-up research (court names, statutes, parties if visible).

CRITICAL: Output ONE JSON object: {{"topics": [<objects>]}}. Each topic object must have:
"title", "provisional_angle", "branch", "priority" (high|medium|low), "seed_phrases" (array of strings).
Do NOT output JSON Schema, $defs, "properties", or merge schema with data.

Example (abbreviated):
{{"topics": [{{"title": "Example headline", "provisional_angle": "Why it matters legally", "branch": "criminal", "priority": "high", "seed_phrases": ["Statute X", "Court Y"]}}]}}
"""
    selected = config.main_model

    def _compile_fallback(_raw: str) -> TopicCompilation:
        return TopicCompilation(
            topics=[
                DiscoveredTopic(
                    title="India legal developments (manual review needed)",
                    provisional_angle="Topic compilation failed; review SERP digest.",
                    branch="other",
                    priority="low",
                    seed_phrases=["India", "court", "legal news"],
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


def _format_serp_digest(
    run_date: str,
    selected_branch: str,
    results_per_query: List[tuple[str, List[dict]]],
) -> str:
    lines: List[str] = [
        f"RUN_DATE: {run_date}",
        f"SELECTED_BRANCH: {selected_branch}",
        "",
        "=== SERP RESULTS (direct legal news queries) ===",
        "",
    ]
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


async def compile_topics_from_serp(
    run_date: str,
    serp_digest: str,
    config: Optional[LLMConfig] = None,
    *,
    selected_branch: str = "",
) -> TopicCompilation:
    _parse_run_date(run_date)
    config = config or create_default_config()
    agent = _init_compiler_agent(config)
    branch_line = f"\nSELECTED_BRANCH (from discovery): {selected_branch}\n" if selected_branch else ""
    result = await ResearchRunner.run(
        agent,
        f"RUN_DATE: {run_date}{branch_line}\nRAW_SNIPPETS_AND_RESULTS:\n{serp_digest[:80000]}",
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
    Random law branch → direct legal-news SERP queries for ``run_date`` → compile topics.
    """
    _parse_run_date(run_date)
    config = config or create_default_config()

    selected_branch = random.choice(LAW_BRANCHES)
    print(
        f"\n[DISCOVERY] Random law branch for this run: {selected_branch}",
        flush=True,
    )

    queries = _build_direct_queries(run_date, selected_branch)
    queries = queries[: max(1, max_discovery_searches)]

    pairs = await _search_queries(queries, max_concurrent=max_concurrent_searches)
    digest = _format_serp_digest(run_date, selected_branch, pairs)
    print(
        f"\n[DISCOVERY] Direct discovery finished: {len(pairs)} SERP call(s).",
        flush=True,
    )
    return await compile_topics_from_serp(
        run_date,
        digest,
        config=config,
        selected_branch=selected_branch,
    )


def topic_title_key(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s[:200]
