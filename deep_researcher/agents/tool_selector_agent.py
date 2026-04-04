"""
Agent used to determine which specialized agents should be used to address knowledge gaps.

For MRO research the strategy prioritises:
  - FAA/EASA/NTSB regulatory and incident databases
  - Aviation fleet databases (ch-aviation, planespotters, cirium)
  - OEM and MRO industry publications (Aviation Week, FlightGlobal, MRO Network)
  - FAA Federal Register for Airworthiness Directives

Input format:
===========================================================
ORIGINAL QUERY: <original user query>

KNOWLEDGE GAP TO ADDRESS: <knowledge gap that needs to be addressed>

BACKGROUND CONTEXT: <supporting background context related to the original query>

HISTORY OF ACTIONS, FINDINGS AND THOUGHTS: <a log of prior iterations>
===========================================================

The Agent:
1. Analyses the knowledge gap to determine which agents are best suited
2. Returns an AgentSelectionPlan with a list of AgentTask objects
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from ..llm_config import LLMConfig, model_supports_structured_output
from .baseclass import ResearchAgent
from .utils.parse_output import create_type_parser


class AgentTask(BaseModel):
    """A task for a specific agent to address knowledge gaps"""
    gap: Optional[str] = Field(description="The knowledge gap being addressed", default=None)
    agent: str = Field(description="The name of the agent to use")
    query: str = Field(description="The specific query for the agent")
    entity_website: Optional[str] = Field(
        description="The website of the entity being researched, if known",
        default=None
    )


class AgentSelectionPlan(BaseModel):
    """Plan for which agents to use for knowledge gaps"""
    tasks: List[AgentTask] = Field(description="List of agent tasks to address knowledge gaps")


INSTRUCTIONS = f"""
You decide which agents should address an MRO research knowledge gap.

AVAILABLE AGENTS:
- WebSearchAgent: Web search (Bright Data SERP → Google). Use for any public source.
- SiteCrawlerAgent: Crawl a specific URL directly (requires entity_website). Use when you
  already know the exact page to retrieve.

MRO RESEARCH STRATEGY — follow this priority order:

1. FLEET EXPOSURE gaps:
   - WebSearchAgent: "site:ch-aviation.com <aircraft> fleet statistics"
   - WebSearchAgent: "<aircraft> <engine> total fleet size operators 2024"
   - SiteCrawlerAgent on ch-aviation.com or planespotters.net if URL known

2. INCIDENT / SDR SIGNAL gaps:
   - WebSearchAgent: "site:av-info.faa.gov <aircraft> <engine> service difficulty reports"
   - WebSearchAgent: "FAA SDR <engine model> <part> recurring issues"
   - WebSearchAgent: "NTSB <aircraft> <engine> incident report"
   - WebSearchAgent: "EASA occurrence report <aircraft> <engine>"

3. AIRWORTHINESS DIRECTIVE gaps:
   - WebSearchAgent: "site:federalregister.gov airworthiness directive <engine model>"
   - WebSearchAgent: "FAA AD <engine> <part> 2020 2021 2022 2023 2024"
   - WebSearchAgent: "EASA AD <engine model> <part> mandatory"
   - SiteCrawlerAgent: https://rgl.faa.gov/Regulatory_and_Guidance_Library/rgAD.nsf/

4. MODULE / SUBCOMPONENT OPPORTUNITY gaps:
   - WebSearchAgent: "<engine> HPT blade repair MRO demand"
   - WebSearchAgent: "<engine> LLP life limited parts cycle requirements"
   - WebSearchAgent: "<engine> <module> shop visit cost overhaul"

5. SUPPLIER / OEM RISK gaps:
   - WebSearchAgent: "<OEM name> financial stability production capacity 2024"
   - WebSearchAgent: "<engine part> supply chain disruption shortage"

6. COMPETITIVE LANDSCAPE gaps:
   - WebSearchAgent: "MRO providers <engine> overhaul market share"
   - WebSearchAgent: "<engine> shop visit MRO providers network"

GUIDELINES:
- Use targeted aviation-specific queries (4-8 words)
- Prioritise .gov/.faa/.easa sources for regulatory data
- Prefer site: operators for known databases (federalregister.gov, ch-aviation.com, av-info.faa.gov)
- Avoid repeating queries that already returned results — check history first
- Do NOT retry URLs that returned errors
- 1-2 WebSearchAgent tasks per iteration is usually sufficient; add SiteCrawlerAgent only when
  you have a specific, known URL that is likely to have structured data

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
        output_parser=create_type_parser(AgentSelectionPlan) if not model_supports_structured_output(selected_model) else None
    )
