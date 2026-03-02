"""
Agent that fetches and reads web page content using the Jina Reader API tools.

Two tools available:
- fetch_page_content: Fetches a single known URL with full JS rendering (r.jina.ai)
- jina_search: Searches the web and returns FULL rendered content of top 5 results (s.jina.ai)

Use this agent when:
1. You have a direct product URL and need to extract its price/specs (use fetch_page_content)
2. You need to find + read product listings in one step without just getting snippets (use jina_search)
"""

from ...tools.jina_reader import fetch_page_content, jina_search
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


INSTRUCTIONS = f"""You are a web page content extraction agent powered by the Jina Reader API.
You have two tools:

1. fetch_page_content(url, target_selector, wait_for_selector, timeout, with_links_summary, respond_with)
   - Fetches a single known URL using headless Chrome (full JavaScript rendering).
   - Use when you have a DIRECT product URL and need to read the actual page content.
   - For price extraction on ecommerce pages, this is ALWAYS preferred over searching.
   - The tool auto-detects CSS price selectors for Amazon, Flipkart, BestBuy, Walmart, etc.
   - Set timeout=30 for slow-loading SPAs. Set with_links_summary=True if you need related URLs.
   - Set target_selector to a CSS selector (e.g. ".a-price") to focus on a specific page element.

2. jina_search(query, site, respond_with)
   - Searches the web and returns the FULL rendered content of top 5 result pages.
   - Unlike WebSearchAgent, this returns actual page content—not just title/snippet.
   - Use for in-site product search: set site="flipkart.com" and query="OnePlus Nord Buds 3 Pro".
   - Better than WebSearchAgent when you know which site to search but don't have the exact URL.

WORKFLOW:
- If you have a direct URL → call fetch_page_content with that URL.
- If you need to find a product on a specific site → call jina_search with site parameter.
- Call tools only as many times as needed — do not repeat the same URL fetch.

FROM THE RETURNED CONTENT, EXTRACT AND REPORT:
- Product name / title (exactly as shown)
- Price (exact amount with currency symbol — e.g. ₹7,499 or $299.99)
- Availability / stock status
- Key specs (model number, storage, color, etc.)
- Source URL

If the page returns an error, insufficient content, or no price data:
- State "Could not retrieve content from [URL]" or "Price not found on page".
- Do NOT guess or estimate prices.

Always include the source URL in your citations.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""


def init_page_fetch_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="PageFetcherAgent",
        instructions=INSTRUCTIONS,
        tools=[fetch_page_content, jina_search],   # Both Jina tools available
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None,
    )
