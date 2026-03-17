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
You decide which agents should address a research knowledge gap.

AVAILABLE AGENTS:
- WebSearchAgent: Web search for information (can use multiple times with different queries)
- SiteCrawlerAgent: Crawl a specific website for information (requires entity_website URL)
- EmailValidationAgent: Validate email addresses and patterns using SendGrid
- ProductPriceAgent: Fetch e-commerce product page via Kameleo (anti-bot bypass) and extract comprehensive product information including title, specs, and price. REQUIRES entity_website = exact product URL (e.g. https://www.homedepot.com/p/...). Use ONLY when you have a direct product URL available.

STRATEGY FOR PRICE COMPARISON RESEARCH - ITERATION-BY-ITERATION:

ITERATION 1 - Get Source Product Details:
- Query: Extract source product title, specs, and price from the TARGET URL
- Use: ProductPriceAgent with entity_website = the exact TARGET PRODUCT URL provided in the query
- Output: Title, Specifications, Current Price, Price Context (to determine if sale/original price)
- Do NOT search for competitors in iteration 1 - ONLY extract source details

ITERATIONS 2+ - Find and Extract Competitor Prices:
- Query: Find competitor product URLs (e.g., "Find Frigidaire FRSS2623AS on Amazon")
- Step 1: Use WebSearchAgent to find competitor product URLs
  * Query format: "Frigidaire FRSS2623AS site:amazon.com" or "Frigidaire FRSS2623AS price site:walmart.com"
  * This discovers the direct URLs on competitor sites
- Step 2: Once you have competitor URLs, use ProductPriceAgent on each URL
  * entity_website = the discovered competitor URL
  * Extract: Title confirmation, Price, Stock status, Seller info

KEY RULES:
1. ProductPriceAgent REQUIRES a direct product URL (entity_website parameter)
   - Do NOT call ProductPriceAgent without a URL
   - If you only have a search query, use WebSearchAgent first to find the URL
2. One ProductPriceAgent call per iteration for reliability
3. In Iteration 1, ONLY get source details - do not search for competitors
4. Starting Iteration 2, search for competitors using WebSearchAgent first, then extract prices

STRATEGY FOR EMAIL PATTERN RESEARCH:
1. FIRST: Use WebSearchAgent to search RocketReach directly for employee data
   - Queries like: "site:rocketreach.co [company name] employees email"
   - RocketReach has comprehensive employee databases and is faster than searching company sites
2. THEN: Use WebSearchAgent to search for company official website
3. THEN: Use SiteCrawlerAgent to crawl company website if needed
4. ONLY AFTER: Use crawl for LinkedIn or other sources
5. FINALLY: Use EmailValidationAgent to validate discovered emails

GUIDELINES:
- Be strategic: prioritize different approaches to avoid repetition
- Use targeted, different queries that address different aspects
- Avoid duplicate or overlapping queries
- AVOID crawling URLs that already failed - check history for error responses
- If a URL returned an error, do NOT retry it - try a different source
- Study the action history to avoid repeating failed approaches
- Focus on fewer, more targeted searches rather than many similar ones
- Be concise with queries (3-6 words)

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
