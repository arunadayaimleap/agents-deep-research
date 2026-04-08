"""
Knowledge-gap and tool-selection agents for India-focused legal news / article research.

Used by IterativeResearcherIndiaLegal. Search jurisdiction is India only; writing style is
formal legal English. Tool strategy mixes indirect news discovery with targeted Indian legal
sources (courts, tribunals, prosecution agencies).
"""

from pydantic import BaseModel, Field
from typing import List

from .baseclass import ResearchAgent
from ..india_legal_discovery import LAW_BRANCHES
from ..llm_config import LLMConfig, model_supports_structured_output
from .utils.parse_output import create_type_parser


class LegalArticleFollowUp(BaseModel):
    """A follow-up article topic to enqueue after the current piece is complete."""

    title: str = Field(description="Short working title for the next article")
    headline_angle: str = Field(description="One-line editorial angle")
    branch: str = Field(
        description="Legal branch id, one of: " + ", ".join(LAW_BRANCHES),
    )
    relationship: str = Field(
        description=(
            "Link to current topic: e.g. SISTER_CASE | STATUTORY_HOOK | "
            "ENFORCEMENT_ANGLE | TRIBUNAL_TRACK | POLICY_FOLLOW_ON | INSTITUTIONAL_ACCOUNTABILITY"
        )
    )
    reason: str = Field(description="Why this follow-up matters for Indian readers")
    priority: str = Field(default="medium", description="high | medium | low")


class LegalIndiaKnowledgeGapOutput(BaseModel):
    research_complete: bool = Field(
        description="True when findings support a publishable legal analysis with adequate sourcing"
    )
    outstanding_gaps: List[str] = Field(
        description="Up to 3 concrete gaps; empty when research_complete"
    )
    related_legal_topics: List[LegalArticleFollowUp] = Field(
        default_factory=list,
        description=(
            "ONLY when research_complete=True: up to 5 distinct follow-on article topics "
            "for the daily queue (different case, statute, institution, or branch)."
        ),
    )


GAP_INSTRUCTIONS = """
You evaluate India-focused legal research for a planned analytical news-style article.

Jurisdiction: India only (Supreme Court, High Courts, District Courts, NCLT/NCLAT, ITAT, SAT,
tribunals, CBI/ED/SFIO where relevant, statutory commissions).

BACKGROUND may include **CASE RESOLUTION (pre-research)** with status, identifiers verbatim from the query, and disambiguation warnings — align gaps and completeness checks with that anchor.

ITERATION 1 — DIARY / CASE IDENTIFIERS (when "Current Iteration Number" in the prompt is 1):
- Unless the ORIGINAL QUERY already names a verified diary number, case number, or equivalent listing id from a primary source, keep research_complete false.
- **outstanding_gaps[0]** MUST explicitly task the next tool run with finding the **diary number** (diary no. / diary) where Indian practice uses it, and/or **case registration number**, **SLP/CA/appeal/civil appeal number**, or **official listing/cause-list identifier** for the matter. Name parties, court or tribunal, and year in the gap string so WebSearch can target them.
- Put identifier discovery first; do not use the first gap slot only for generic background.

TASK:
1. Review findings. Set research_complete true only when ALL are adequately sourced:
   - Primary fact pattern (parties, forum, stage of proceedings if reported)
   - For **litigation topics**: reporter-style identifiers where available — SCC / SCC OnLine / AIR / tribunal reporter cites, **coram and counsel full names** (as in the judgment cause title / header), decision date, diary or appeal numbers, headnote or catchwords from SCC Online digests, Indian Kanoon, or official orders
   - Legal issues and applicable statutory/constitutional hooks (as reported)
   - If cases are cited: court, bench context, and ratio or relief as reported in sources
   - Enough **dated events** to support a **chronology table** (orders, appeals, key filings) and enough **cited precedents** (cases/statutes the story turns on) for dedicated article sections
   - Counter-positions or limitations visible in sources
2. If incomplete: up to 3 concrete strings in outstanding_gaps for the next tool runs.
3. If complete: related_legal_topics with up to 5 follow-on article ideas (entities/themes from findings).

Do not fabricate citations or holdings. If sources only give partial facts, keep research_complete false.

CRITICAL — OUTPUT FORMAT:
- Respond with ONE JSON object containing YOUR ASSESSMENT (data only).
- Do NOT output JSON Schema, $defs, "properties", "title", "type": "object", or any schema metadata.
- Do NOT copy a schema from the prompt; only concrete field values.

Incomplete example:
{"research_complete": false, "outstanding_gaps": ["Find the reported court forum and case number", "Confirm statutory sections cited in news"], "related_legal_topics": []}

Complete example (abbreviated):
{"research_complete": true, "outstanding_gaps": [], "related_legal_topics": [{"title": "Follow-on topic", "headline_angle": "Angle", "branch": "civil", "relationship": "SISTER_CASE", "reason": "Why", "priority": "medium"}]}
"""


def _gap_output_fallback(raw: str) -> LegalIndiaKnowledgeGapOutput:
    """When the model returns unparseable JSON or schema echo; keep the loop useful."""
    return LegalIndiaKnowledgeGapOutput(
        research_complete=False,
        outstanding_gaps=[
            "Re-run sourcing: previous evaluator output was not valid JSON. "
            "Tighten queries toward primary court portals, case identifiers, and official orders."
        ],
        related_legal_topics=[],
    )


def init_legal_india_knowledge_gap_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.reasoning_model
    return ResearchAgent(
        name="LegalIndiaKnowledgeGapAgent",
        instructions=GAP_INSTRUCTIONS,
        model=selected_model,
        output_type=LegalIndiaKnowledgeGapOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(
            LegalIndiaKnowledgeGapOutput,
            fallback_on_validation_error=_gap_output_fallback,
        )
        if not model_supports_structured_output(selected_model)
        else None,
    )


def init_legal_india_tool_selector_agent(config: LLMConfig) -> ResearchAgent:
    from .tool_selector_agent import AgentSelectionPlan

    selected_model = config.reasoning_model
    instructions = """
You choose tools to close a knowledge gap for INDIAN legal article research.

AVAILABLE AGENTS:
- WebSearchAgent: Bright Data / Google SERP.
- SiteCrawlerAgent: Fetch a specific URL when entity_website is the exact page to read.
- CourtSearchAgent: Indian judgments and citations (indiankanoon.org, sci.gov.in).

BACKGROUND may include a **CASE RESOLUTION (pre-research)** block with `Suggested first search seed` / `tool_search_seed`.
On **iteration 1**, incorporate that seed into at least one WebSearch query when it fits the active gap (do not ignore it unless it conflicts with the gap).

FIRST ITERATION (when "Current Iteration Number" is 1, or HISTORY has no `<findings>` yet):
- **Mandatory focus:** WebSearchAgent and CourtSearchAgent queries MUST aim to surface **diary number** (diary no.), **case number**, **registration number**, **SLP/CA/appeal** numbers, or **cause list / listing** references for the matter in ORIGINAL QUERY.
- Combine concrete nouns (party names, judge, city, institution) with identifier keywords: "diary number", "diary no", "case no", "registration", "SLP", "civil appeal", "cause list", "listed on", "item no".
- After identifiers are in HISTORY, later iterations may narrow to ratio, orders, and precedent.

INDIA LEGAL RESEARCH STRATEGY (priority order):

1) INDIRECT NEWS / OFFICIAL SIGNALS (do not only search "legal news" or "latest judgment"):
   - WebSearchAgent: site:livelaw.in OR site:barandbench.com OR site:legallyindia.com
     plus concrete nouns from the gap (judge, city, institution, statute short title).
   - WebSearchAgent: ministry / regulator / PIB site:gov.in with subject keywords.

2) COURT OUTPUTS & REPORTER METADATA (SCC-style headnotes):
   - WebSearchAgent: **site:scconline.com** with case name, citation, or tribunal + party keywords (blog digests, SCC Times, public headnote text).
   - CourtSearchAgent: case names, "versus" citations, neutral party labels + court name (include scconline in summary when found).
   - WebSearchAgent: site:sci.gov.in OR site:indiankanoon.org with technical query strings (citation, appeal number).

3) TRIBUNALS / AGENCIES: NCLT NCLAT ITAT CESTAT CBI ED SFIO with India-specific keywords.

4) SiteCrawlerAgent only when a specific judgment or court PDF URL is already known from history.

RULES: 6–14 word queries; 1–3 tasks per iteration; do not repeat failed queries verbatim.

CRITICAL: Output ONE JSON object with a "tasks" array (your plan only). Do NOT output JSON Schema,
$defs, or "properties" blocks.

Example:
{"tasks": [{"gap": "Find reported ratio", "agent": "WebSearchAgent", "query": "site:sci.gov.in party names Supreme Court 2024", "entity_website": null}]}
"""

    def _plan_fallback(raw: str) -> AgentSelectionPlan:
        from .tool_selector_agent import AgentTask

        return AgentSelectionPlan(
            tasks=[
                AgentTask(
                    gap="Recover from invalid tool-selector JSON",
                    agent="WebSearchAgent",
                    query="India site:livelaw.in site:barandbench.com",
                    entity_website=None,
                )
            ]
        )

    return ResearchAgent(
        name="LegalIndiaToolSelectorAgent",
        instructions=instructions,
        model=selected_model,
        output_type=AgentSelectionPlan if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(
            AgentSelectionPlan,
            fallback_on_validation_error=_plan_fallback,
        )
        if not model_supports_structured_output(selected_model)
        else None,
    )
