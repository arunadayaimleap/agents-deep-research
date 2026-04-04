"""
Knowledge-gap and tool-selection agents for India-focused legal news / article research.

Used by IterativeResearcherIndiaLegal. Search jurisdiction is India only; writing style is
formal legal English. Tool strategy mixes indirect news discovery with targeted Indian legal
sources (courts, tribunals, prosecution agencies).
"""

from pydantic import BaseModel, Field
from typing import List

from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from .utils.parse_output import create_type_parser


class LegalArticleFollowUp(BaseModel):
    """A follow-up article topic to enqueue after the current piece is complete."""

    title: str = Field(description="Short working title for the next article")
    headline_angle: str = Field(description="One-line editorial angle")
    branch: str = Field(
        description="Legal branch: e.g. constitutional, criminal, civil, taxation, corporate, labour, environmental, arbitration, administrative"
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


GAP_INSTRUCTIONS = f"""
You evaluate India-focused legal research for a planned analytical news-style article.

Jurisdiction: India only (Supreme Court, High Courts, District Courts, NCLT/NCLAT, ITAT, SAT,
tribunals, CBI/ED/SFIO where relevant, statutory commissions).

TASK:
1. Review findings. Decide if research_complete is true only when ALL are adequately sourced:
   - Primary fact pattern (parties, forum, stage of proceedings if reported)
   - Legal issues and applicable statutory/constitutional hooks (as reported)
   - If cases are cited: court, bench context, and ratio or relief as reported in sources
   - Counter-positions or limitations visible in sources
2. If incomplete: up to 3 outstanding_gaps that the next tool runs should close.
3. If complete: related_legal_topics with up to 5 follow-on article ideas grounded in entities
   or themes in the findings (not generic placeholders).

Do not fabricate citations or holdings. If sources only give partial facts, keep research_complete false.

Output valid JSON only:
{LegalIndiaKnowledgeGapOutput.model_json_schema()}
"""


def init_legal_india_knowledge_gap_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model
    return ResearchAgent(
        name="LegalIndiaKnowledgeGapAgent",
        instructions=GAP_INSTRUCTIONS,
        model=selected_model,
        output_type=LegalIndiaKnowledgeGapOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(LegalIndiaKnowledgeGapOutput)
        if not model_supports_structured_output(selected_model)
        else None,
    )


def init_legal_india_tool_selector_agent(config: LLMConfig) -> ResearchAgent:
    from .tool_selector_agent import AgentSelectionPlan

    selected_model = config.reasoning_model
    instructions = f"""
You choose tools to close a knowledge gap for INDIAN legal article research.

AVAILABLE AGENTS:
- WebSearchAgent: Bright Data / Google SERP.
- SiteCrawlerAgent: Fetch a specific URL when entity_website is the exact page to read.
- CourtSearchAgent: Indian judgments and citations (indiankanoon.org, sci.gov.in).

INDIA LEGAL RESEARCH STRATEGY (priority order):

1) INDIRECT NEWS / OFFICIAL SIGNALS (do not only search "legal news" or "latest judgment"):
   - WebSearchAgent: site:livelaw.in OR site:barandbench.com OR site:legallyindia.com
     plus concrete nouns from the gap (judge, city, institution, statute short title).
   - WebSearchAgent: ministry / regulator / PIB site:gov.in with subject keywords.

2) COURT OUTPUTS:
   - CourtSearchAgent: case names, "versus" citations, neutral party labels + court name.
   - WebSearchAgent: site:sci.gov.in OR site:indiankanoon.org with technical query strings.

3) TRIBUNALS / AGENCIES: NCLT NCLAT ITAT CESTAT CBI ED SFIO with India-specific keywords.

4) SiteCrawlerAgent only when a specific judgment or court PDF URL is already known from history.

RULES: 6–14 word queries; 1–3 tasks per iteration; do not repeat failed queries verbatim.

Output ONLY valid JSON matching:
{AgentSelectionPlan.model_json_schema()}
"""

    return ResearchAgent(
        name="LegalIndiaToolSelectorAgent",
        instructions=instructions,
        model=selected_model,
        output_type=AgentSelectionPlan if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(AgentSelectionPlan)
        if not model_supports_structured_output(selected_model)
        else None,
    )
