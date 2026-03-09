"""
Agent used to produce an initial outline of the report, including a list of section titles and the key question to be 
addressed in each section.

The Agent takes as input a string in the following format:
===========================================================
QUERY: <original user query>
===========================================================

The Agent then outputs a ReportPlan object, which includes:
1. A summary of initial background context (if needed), based on web searches and/or crawling
2. An outline of the report that includes a list of section titles and the key question to be addressed in each section
"""

from pydantic import BaseModel, Field
from typing import List
from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from .tool_agents.crawl_agent import init_crawl_agent
from .tool_agents.search_agent import init_search_agent
from .utils.parse_output import create_type_parser
from datetime import datetime


class ReportPlanSection(BaseModel):
    """A section of the report that needs to be written"""
    title: str = Field(description="The title of the section")
    key_question: str = Field(description="The key question to be addressed in the section")


class ReportPlan(BaseModel):
    """Output from the Report Planner Agent"""
    background_context: str = Field(description="A summary of supporting context that can be passed onto the research agents")
    report_outline: List[ReportPlanSection] = Field(description="List of sections that need to be written in the report")
    report_title: str = Field(description="The title of the report")


INSTRUCTIONS = f"""
Create a report outline for the research query.

AVAILABLE TOOLS:
- web_search: Search the web for background information
- crawl_website: Crawl a website for background information

TASK:
1. (Optional) Use tools to gather 1-2 paragraphs of background context (use at most 2 tool calls)
2. Create a report outline with 3-5 sections, each with a title and key question
3. Provide a report title

Output ONLY valid JSON following this schema:
{ReportPlan.model_json_schema()}
"""

def init_planner_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.reasoning_model
    search_agent = init_search_agent(config)
    crawl_agent = init_crawl_agent(config)

    return ResearchAgent(
            name="PlannerAgent",
            instructions=INSTRUCTIONS,
        tools=[
            search_agent.as_tool(
                tool_name="web_search",
                tool_description="Use this tool to search the web for information relevant to the query - provide a query with 3-6 words as input"
            ),
            crawl_agent.as_tool(
                tool_name="crawl_website",
                tool_description="Use this tool to crawl a website for information relevant to the query - provide a starting URL as input"
            )
        ],
        model=selected_model,
        output_type=ReportPlan if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ReportPlan) if not model_supports_structured_output(selected_model) else None
    )
