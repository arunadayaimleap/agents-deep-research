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
from typing import List, Optional, Literal
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


class ResearchAction(BaseModel):
    agent: Literal["WebSearchAgent", "SiteCrawlerAgent", "PageFetcherAgent", "BrightDataFetcherAgent", "BrightDataSERPAgent"] = Field(
        description="The specific specialized agent to call"
    )
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
- BrightDataSERPAgent: Replaces standard WebSearch. Fetches rich Google Search JSON (Organic results with descriptions, Shopping Prices, AI Overviews) via BrightData. Use this for discovering the source product details, identifying competitors, AND searching for competitor prices. ALWAYS prioritize this first for any search query instead of WebSearchAgent.
  * Search Format: Treat this as a strictly keyword-based web search (e.g., query='"OnePlus Nord Buds 3R" "Reliance Digital" price India'). Do NOT use conversational AI prompts.
  * RESTRICTION: When searching for competitor prices, DO THIS ONE COMPETITOR AT A TIME. Do NOT run multiple competitor searches in parallel.
  * INDIRECT SEARCH FALLBACK: If direct searches on a competitor domain fail or don't yield prices, you MUST use this tool to search indirectly. Query deal forums (e.g., DesiDime, Tech4All), price trackers, or tech news articles to find the price and availability.
- WebSearchAgent: General web search fallback. ONLY use this if BrightDataSERPAgent fails repeatedly.
- SiteCrawlerAgent: Crawl multiple pages of a specific website. Use when you need to explore a site's structure or find listings across many pages.
- PageFetcherAgent: Fetches the FULLY RENDERED content of a single known URL using the Jina Reader API. DO NOT use this for eCommerce websites (Amazon, Flipkart, BestBuy, Walmart, Croma, JioMart, etc.) — they WILL block it and return 404 or Captcha walls. NEVER use this for Step 1 Source Discovery. ONLY use this for non-ecommerce blogs, press releases, or standard articles.
- BrightDataFetcherAgent: Fetches a product URL via BrightData residential proxies with bot-bypass. Use this if you absolutely MUST fetch the raw HTML content of an eCommerce product page and the BrightDataSERPAgent wasn't enough. Set entity_website to the exact product URL.

PRICE COMPARISON FLOW (Strict Order):
  STEP 1 — Source Product Discovery (1 search): Use BrightDataSERPAgent ONLY to find the exact model, specs, and source price from the provided URL/product name. (e.g., query="Flipkart OnePlus Nord Buds 3R specs price"). DO NOT use PageFetcherAgent for your very first step. Rely on the SERP AI Overview to unpack the product details.
  STEP 2 — Competitor Identification (1 search): Use BrightDataSERPAgent to find the top 3-5 competitor platforms in that country.
  STEP 3 — Competitor Price Search (1 search at a time): Use BrightDataSERPAgent to find the price on ONE competitor (e.g. query="[product] site:[competitor.com]").
           - You MUST use the Google site: operator to restrict results. (CORRECT: "Whirlpool J3KHVG33QL site:walmart.com", INCORRECT: "Whirlpool walmart").
           - You MUST do only ONE competitor search per iteration. This allows deep analysis of the rich SERP JSON. Do not parallelize these.
  STEP 4 — Direct URL Fetch (Optional/Fallback): If SERP does not contain the explicit price in Shopping/Organic snippets, use PageFetcherAgent to read the discovered URL.

PRIORITY RULES:
- Use BrightDataSERPAgent for all general discovery and price searching.
- NEVER use PageFetcherAgent as your first step. Always start with BrightDataSERPAgent to get the AI overview.
- When doing Step 3, schedule ONLY ONE BrightDataSERPAgent call at a time to max out result quality.
- Use PageFetcherAgent only if you already have the exact URL but SERP didn't expose the price.
- Use BrightDataFetcherAgent as FALLBACK if a PageFetcherAgent call returned: "blocked", "CAPTCHA", "sign in", "robot", empty content, or no price found.
- Do NOT re-try PageFetcherAgent simply because a page fetch failed — try BrightDataFetcherAgent instead.

General Guidelines:
- Aim to call at most 2 agents at a time in your planning to respect the one-by-one rule.
- Be specific and precise with agent queries.
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
