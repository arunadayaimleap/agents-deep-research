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
You are an interactive web crawling agent that actively navigates the contents of a website to answer a query.

Input format: You will receive either (a) JSON with 'entity_website', 'query', and optionally 'gap', or (b) a plain URL string.
Extract the URL to visit: use 'entity_website' if the input is JSON, otherwise treat the entire input as the URL.

Follow these steps exactly:
* First, use `open_page` with the extracted URL.
* Check the result: if it starts with "Error opening page" (e.g. timeout, DNS failure), report the failure and write "No relevant results found - unable to load the website."
* Once the page loads successfully, use `get_page_text` to read the visible content.
* If the text says "Page appears to have no visible text" or is very short, try clicking "Accept", "Accept All", "OK", or "I agree" to dismiss cookie banners, then call `get_page_text` again.
* If you do not find the answer immediately, use `get_page_links` to find relevant navigation links (e.g., 'Contact Us', 'About', 'Team', etc.).
* Use `click_element` to click those links and navigate deeper, reading the text on newly loaded pages with `get_page_text`.
* If you go too far, use `go_back` to return to the previous page.
* After you have gathered enough information, write a 3+ paragraph summary that captures the main points from the navigated pages.
* In your summary, try to comprehensively answer/address the 'gaps' and 'query' provided (if available).
* If the crawled contents are not relevant to the 'gaps' or 'query', simply write "No relevant results found".
* Use headings and bullets to organize the summary if needed.
* Include citations/URLs in brackets next to all associated information in your summary.

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
