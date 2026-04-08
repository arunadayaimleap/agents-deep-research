"""
Agent used to crawl a website and return the results.

The CrawlAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple URL string as input

The Agent then:
1. Uses the crawl_website tool to crawl the website
2. Writes a summary of the crawled contents
3. Includes citations/URLs in brackets next to information sources
4. Returns the formatted summary as JSON
"""

from agents import function_tool

from ...tools.exa_tools import exa_get_url_text
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


@function_tool
async def crawl_website(url: str) -> str:
    """Crawl a website and extract its content using Exa page contents.

    Args:
        url: The starting URL to crawl

    Returns:
        Plain text from the webpage or an error message
    """
    return await exa_get_url_text(url, max_length=10000)


INSTRUCTIONS = f"""You are a web crawling agent that extracts information from websites.

OBJECTIVE:
Given a URL:
1. Use the crawl_website tool ONCE with the provided URL
2. Analyze the crawled content
3. Write a comprehensive summary of the findings
4. Include all relevant citations and the URL

GUIDELINES:
- Use the crawl_website tool ONLY ONCE per task
- Do NOT crawl multiple pages or try to crawl variations of the URL
- Use the URL as provided - do NOT modify it
- Write a thorough summary that answers the query
- Include citations [URL] for information sources
- If content is not relevant, state that clearly
- Use headings and bullets to organize if helpful

CRITICAL:
- Output ONLY valid JSON
- Do not include any narrative, thinking, or tool invocations
- The JSON must have "output" and "sources" fields
- Do not output anything except the JSON

{ToolAgentOutput.model_json_schema()}
"""

def init_crawl_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="SiteCrawlerAgent",
        instructions=INSTRUCTIONS,
        tools=[crawl_website],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(
            ToolAgentOutput,
            fallback_on_validation_error=lambda raw: ToolAgentOutput(output=raw, sources=[]),
        ) if not model_supports_structured_output(selected_model) else None
    )
