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
- EmailValidationAgent: Validate email addresses and patterns using SendGrid (requires email_addresses or pattern to test)

GUIDELINES:
- Be strategic: use targeted, different queries that address different aspects of the gap
- Avoid duplicate or overlapping queries - if you tried a similar search before, try a different angle
- AVOID crawling URLs that already failed - check the history for error responses and don't retry them
- If a URL returned an error or empty response, do NOT ask to crawl it again
- Try different URLs instead of retrying failed ones
- Prefer both WebSearchAgent AND SiteCrawlerAgent in parallel for company research
- For email pattern research: Use SiteCrawlerAgent to crawl LinkedIn company pages and employee profiles
- LinkedIn is an excellent source for discovering real employee names and email addresses
- AFTER finding potential email addresses, use EmailValidationAgent to validate them
- EmailValidationAgent sends test emails and checks delivery status to confirm addresses work
- Be concise with queries (3-6 words)
- SiteCrawlerAgent requires a full URL (e.g. https://example.com/about or https://www.linkedin.com/company/company-name)
- Study the action history to avoid repeating failed approaches
- Focus on fewer, more targeted searches rather than many similar ones

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
