"""
Agent used to determine which specialized agents should be used to address knowledge gaps.

The Agent takes as input a string in the following format:
===========================================================
ORIGINAL QUERY: <original user query>

KNOWLEDGE GAP TO ADDRESS: <knowledge gap that needs to be addressed>

BACKGROUND CONTEXT: <supporting background context related to the original query>

HISTORY OF ACTIONS, FINDINGS AND THOUGHTS: <a log of prior iterations of the research process>
===========================================================

The Agent then:
1. Analyzes the knowledge gap to determine which agents are best suited to address it
2. Returns an AgentSelectionPlan object containing a list of AgentTask objects

The available agents are:
- WebSearchAgent: General web search for broad topics
- SiteCrawlerAgent: Crawl the pages of a specific website to retrieve information about it
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from ..llm_config import LLMConfig, model_supports_structured_output
from datetime import datetime
from .baseclass import ResearchAgent
from .utils.parse_output import create_type_parser


class AgentTask(BaseModel):
    """A task for a specific agent to address knowledge gaps"""
    gap: Optional[str] = Field(description="The knowledge gap being addressed", default=None)
    agent: str = Field(description="The name of the agent to use")
    query: str = Field(description="The specific query for the agent")
    entity_website: Optional[str] = Field(description="The website of the entity being researched, if known", default=None)


class AgentSelectionPlan(BaseModel):
    """Plan for which agents to use for knowledge gaps"""
    tasks: List[AgentTask] = Field(description="List of agent tasks to address knowledge gaps")


INSTRUCTIONS = f"""
You are a Tool Selector responsible for determining which specialized agents should address a knowledge gap in a research project.
Today's date is {datetime.now().strftime("%Y-%m-%d")}.

You will be given:
1. The original user query
2. A knowledge gap identified in the research
3. A full history of the tasks, actions, findings and thoughts you've made up until this point in the research process

Your task is to decide:
1. Which specialized agents are best suited to address the gap
2. What specific queries should be given to those agents

Available specialized agents:
- WebSearchAgent: General web search. Use this to find information, discover URLs, identify competitors, or search for a product listing on a specific site.
- SiteCrawlerAgent: Crawl multiple pages of a specific website. Use when you need to explore a site's structure or find listings across many pages.
- PageFetcherAgent: Has TWO capabilities powered by Jina AI:
    (a) fetch_page_content — fetches a single known URL with full JS rendering (headless Chrome). Use when you have a direct product URL and need price/specs/availability. Auto-detects price CSS selectors for Amazon, Flipkart, BestBuy, Walmart, Croma etc. Set entity_website to the product URL.
    (b) jina_search — searches the web AND returns full rendered content of the top 5 result pages (not just snippets). Use when you know the competitor site but not the exact product URL: set query to the product name + model and set entity_website to the competitor domain (e.g. flipkart.com) so it does an in-site search. This is more powerful than WebSearchAgent for price discovery because it reads full page content.

TWO-PHASE RULE for price comparison tasks:
  PHASE 1 — Discovery: Use WebSearchAgent to find the direct product URL on each competitor website.
             Query format: "[product name] [model number] site:[competitor domain]"
             Goal: obtain a direct product page URL per competitor.
  PHASE 2 — Price extraction: Once a direct product URL is known, use PageFetcherAgent (NOT WebSearchAgent) to fetch that URL and extract the confirmed price.
             Set entity_website = the exact product URL. Do NOT search for price — fetch the page.

PRIORITY RULES:
- NEVER use WebSearchAgent to get a price if you already have a direct product URL — use PageFetcherAgent instead.
- NEVER use WebSearchAgent to visit or read a page — it only returns snippets, not page content.
- Use PageFetcherAgent for any gap that says "confirm price", "get price from URL", "read product page", or "fetch page content".
- You can run multiple PageFetcherAgent tasks in parallel (one per competitor URL).

General Guidelines:
- Aim to call at most 3 agents at a time in your final output.
- Be specific and concise (3-6 words) with agent queries.
- Do not repeat the same search if it returned no results previously — try a different query.
- Use the history of actions as a guide to avoid repeating failed approaches.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
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
