"""
CourtSearchAgent: search Indian court/legal websites to resolve case citations.

Uses the same web search tool as WebSearchAgent but with instructions to query
indiankanoon.org, sci.gov.in, and other Indian legal sources.
"""

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.tool_agents import ToolAgentOutput
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output
from ...tools.web_search import create_web_search_tool

INSTRUCTIONS = """You are a legal research assistant that finds Indian case law.

OBJECTIVE:
Given a citation or case name:
1. Use the web_search tool to search Indian legal sources
2. Prefer queries like: site:indiankanoon.org "<citation>"
   or site:sci.gov.in "<case name>"
   or "AIR 1996 SC 1393" OR "(1996) 2 SCC 384"
3. Summarize what you found: case name, court, year, and key outcome if available

GUIDELINES:
- Use the web_search tool ONCE with a targeted query
- Focus on Indian Supreme Court and High Court sources (indiankanoon.org, sci.gov.in, manupatra, SCC Online)
- If the case is not found, say so clearly
- Output valid JSON with "output" (your summary) and "sources" (list of URLs or source names)
"""


def init_court_search_agent(config: LLMConfig) -> ResearchAgent:
    web_search_tool = create_web_search_tool(config)
    return ResearchAgent(
        name="CourtSearchAgent",
        instructions=INSTRUCTIONS,
        tools=[web_search_tool],
        model=config.fast_model,
        output_type=ToolAgentOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(
            ToolAgentOutput,
            fallback_on_validation_error=lambda raw: ToolAgentOutput(output=raw, sources=[]),
        ) if not model_supports_structured_output(config.fast_model) else None,
    )
