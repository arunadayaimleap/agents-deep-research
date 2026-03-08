"""
Agent used to crawl a website and return the results.

Uses Jina Reader to fetch page content. Takes AgentTask JSON or a plain URL string as input.
Fetches URLs with read_url_with_jina and writes a 3+ paragraph summary with citations.
"""

from ...tools.jina_tools import read_url_with_jina
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


INSTRUCTIONS = f"""
You are a web crawling agent that uses Jina Reader to fetch page content. You have one tool: read_url_with_jina.

Input format: You will receive either (a) JSON with 'entity_website', 'query', and optionally 'gap', or (b) a plain URL string.
Extract the URL(s) to fetch: use 'entity_website' if the input is JSON, otherwise treat the entire input as the URL.

Workflow:
1. Use `read_url_with_jina` with the extracted URL. It returns clean markdown content directly.
2. If the result starts with "Error", report the failure and write "No relevant results found - unable to load the website."
3. For multiple pages (e.g. homepage + /contacto + /quienes-somos): call read_url_with_jina for each URL. The tool selector should provide separate tasks for each URL when possible.
4. After gathering content, write a 3+ paragraph summary with citations/URLs in brackets.
5. Include citations/URLs next to all associated information.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""

def init_crawl_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="SiteCrawlerAgent",
        instructions=INSTRUCTIONS,
        tools=[read_url_with_jina],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None
    )
