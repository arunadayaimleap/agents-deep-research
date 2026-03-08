"""
Agent used to crawl a website and return the results.

The SearchAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple starting url string as input

The Agent then:
1. Uses the interactive Playwright browser tools to navigate the given website.
2. Writes a 3+ paragraph summary of the crawled contents
3. Includes citations/URLs in brackets next to information sources
4. Returns the formatted summary as a string
"""

from ...tools.browser_tools import open_page, get_page_text, get_page_links, click_element, go_back
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


INSTRUCTIONS = f"""
You are an interactive web crawling agent. MINIMIZE tool calls - you have limited turns. Be efficient.

Input format: You will receive either (a) JSON with 'entity_website', 'query', and optionally 'gap', or (b) a plain URL string.
Extract the URL to visit: use 'entity_website' if the input is JSON, otherwise treat the entire input as the URL.

Efficient workflow (use as few tool calls as possible):
1. Use `open_page` with the extracted URL.
2. If the result starts with "Error opening page", report the failure and write "No relevant results found - unable to load the website." Then output your summary.
3. Use `get_page_text` to read the content. If it says "Page appears to have no visible text", try clicking "Accept" or "I agree" once, then `get_page_text` again.
4. If the homepage has the answer (emails, contacts, names), write your summary immediately. Do NOT navigate further.
5. If you need more: use `get_page_links` ONCE, then click ONLY 1-2 most relevant links (Contact, About, Quiénes Somos, Contacto, Equipo). Read each with `get_page_text`. Do NOT explore deeply - stop after 1-2 additional pages.
6. Write a 3+ paragraph summary with citations/URLs in brackets.

Critical: Do NOT click many links. Do NOT navigate in circles. Prioritize homepage + Contact/About only. Include citations/URLs in brackets.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""

def init_crawl_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="SiteCrawlerAgent",
        instructions=INSTRUCTIONS,
        tools=[open_page, get_page_text, get_page_links, click_element, go_back],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None
    )
