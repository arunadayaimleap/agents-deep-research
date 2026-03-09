"""
Agent used to crawl a website and return the results.

Uses Bright Data Unlocker API to fetch page content with anti-bot bypass.
Takes AgentTask JSON or a plain URL string as input.
Fetches URLs and writes a summary with citations.
"""

from agents import function_tool
from ...tools.brightdata_tools import brightdata_unlock_url
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


@function_tool
async def read_url_with_brightdata(url: str) -> str:
    """Fetch URL content using Bright Data Unlocker API with markdown extraction.
    
    Args:
        url: The URL to fetch
        
    Returns:
        Clean markdown content or error message
    """
    return await brightdata_unlock_url(url, max_length=10000, data_format="markdown")


INSTRUCTIONS = f"""You are a web crawler that extracts content from websites.

AVAILABLE TOOLS:
1. read_url_with_brightdata - Fetch content from a URL with anti-bot bypass

WORKFLOW:
1. Extract the URL from the input (either from entity_website field or the input itself)
2. Use read_url_with_brightdata to fetch the page content
3. Analyze the content and write a summary
4. Include citations for all information

IMPORTANT:
- For multiple pages: call read_url_with_brightdata for each URL
- Always output valid JSON following this schema:

{ToolAgentOutput.model_json_schema()}
"""

def init_crawl_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="SiteCrawlerAgent",
        instructions=INSTRUCTIONS,
        tools=[read_url_with_brightdata],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None
    )
