"""
Agent that fetches and reads web page content using the Jina Reader API tools.

Two tools available:
- fetch_page_content: Fetches a single known URL with full JS rendering (r.jina.ai)
- jina_search: Searches the web and returns FULL rendered content of top 5 results (s.jina.ai)

Use this agent when:
1. You have a direct product URL and need to extract its price/specs (use fetch_page_content)
2. You need to find + read product listings in one step without just getting snippets (use jina_search)
"""

from ...tools.jina_reader import fetch_page_content
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


INSTRUCTIONS = f"""You are a web page content extraction agent. You fetch the fully JavaScript-rendered
content of a specific product URL using the Jina Reader API (headless Chrome) and extract
structured information from it.

TOOL: fetch_page_content(url, target_selector, wait_for_selector, timeout, with_links_summary, respond_with)
- Fetches a single known URL with full JavaScript rendering.
- Auto-detects CSS price selectors for Amazon, Flipkart, BestBuy, Walmart, Croma, etc.
- Use target_selector (e.g. ".a-price") to focus on a specific element if needed.
- Set timeout=30 for slow-loading pages.

STEPS:
1. Get the target URL from the 'entity_website' field or extract it from the 'query'.
2. Call fetch_page_content with that URL.
3. From the returned content, extract:
   - Product name / title (exactly as shown on the page)
   - Price (exact amount with currency symbol — e.g. ₹7,499 or $299.99)
   - Availability / stock status
   - Key specs (model number, color, storage, etc.)
4. Write a concise summary with the source URL cited.

RULES:
- Only call the tool ONCE per URL.
- If the page returns an error or no price: state "Price not found on page" — do NOT guess.
- Always include the source URL in your output citations.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""


def init_page_fetch_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="PageFetcherAgent",
        instructions=INSTRUCTIONS,
        tools=[fetch_page_content],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None,
    )
