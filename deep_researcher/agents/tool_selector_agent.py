"""
Agent used to determine which specialized agents should be used to address knowledge gaps.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from ..llm_config import LLMConfig, model_supports_structured_output
from datetime import datetime
from .baseclass import ResearchAgent
from .utils.parse_output import create_type_parser


class AgentTask(BaseModel):
    gap: Optional[str] = Field(description="The knowledge gap being addressed", default=None)
    agent: str = Field(description="The name of the agent to use")
    query: str = Field(description="The specific query for the agent")
    entity_website: Optional[str] = Field(description="The website of the entity being researched, if known", default=None)


class AgentSelectionPlan(BaseModel):
    tasks: List[AgentTask] = Field(description="List of agent tasks to address knowledge gaps")


INSTRUCTIONS = f"""
You decide which agents should address a knowledge gap in a **criminal case / true-crime news** research project.
Today's date is {datetime.now().strftime("%Y-%m-%d")}.

AVAILABLE AGENTS:
- WebSearchAgent: Web search (call multiple times with different queries)
- SiteCrawlerAgent: Crawl a specific news or official site (requires entity_website URL)

CRIME NEWS RESEARCH STRATEGY:
1. **Discover top cases:** Search for breaking crime news today — e.g. "major criminal cases news today", "breaking crime news {datetime.now().strftime('%B %Y')}".
2. **Per case:** Search suspect name + charges, victim identity (when public), court date, indictment, arrest affidavit.
3. **Official sources:** Prefer `.gov`, court portals, police press releases, prosecutor statements; use site: when you know the domain.
4. **Verify:** Cross-check with at least two reputable outlets before treating a fact as established.
5. **SiteCrawler:** Use on a known article URL or agency press-release index when search snippets are thin.

GUIDELINES:
- Queries: 3–8 words; include dates or "today" when freshness matters.
- Do not repeat failed queries from history.
- Up to 3 agent tasks per plan.
- Never search for illegal content; stick to public news and legal records.

Output ONLY valid JSON matching this schema:
{AgentSelectionPlan.model_json_schema()}
"""


def init_tool_selector_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.reasoning_model
    return ResearchAgent(
        name="ToolSelectorAgent",
        instructions=INSTRUCTIONS,
        model=selected_model,
        output_type=AgentSelectionPlan if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(AgentSelectionPlan) if not model_supports_structured_output(selected_model) else None,
    )
