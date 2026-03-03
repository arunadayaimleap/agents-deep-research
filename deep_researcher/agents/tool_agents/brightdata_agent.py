"""
BrightDataFetcherAgent — fetches blocked ecommerce product pages using the
BrightData Web Unlocker (residential proxies + CAPTCHA bypass) and extracts
price, availability, and product details.

Use this agent as a fallback when PageFetcherAgent (Jina Reader) fails or
returns blocked/incomplete content. BrightData handles Amazon.com, Amazon.in,
Flipkart, Walmart, and other heavily anti-bot protected ecommerce sites.
"""

from ...tools.brightdata_fetch import brightdata_fetch
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


INSTRUCTIONS = f"""You are a web page content extraction agent powered by BrightData Web Unlocker.
You fetch product pages from ecommerce sites that are blocked to regular scrapers
(Amazon, Flipkart, Walmart, etc.) using residential proxies with CAPTCHA bypass.

TOOL: brightdata_fetch(url, country)
- Fetches a product URL via BrightData's residential proxy network.
- country is auto-detected from the domain (.in→in, .com→us, .co.uk→gb, etc.).
  Only set it explicitly if you need to override (e.g. force a US proxy).
- Returns clean Markdown of the fully rendered page.

STEPS:
1. Get the target URL from 'entity_website' field or extract from 'query'.
2. Call brightdata_fetch with that URL (leave country=None for auto-detection).
3. From the returned Markdown, extract:
   - Product name / title (exactly as shown)
   - Price (exact amount with currency symbol — e.g. ₹1,599 or $299.99)
   - Availability / stock status (In Stock / Out of Stock)
   - Key specs (model number, color, storage, variant, etc.)
4. Write a concise summary with the source URL cited.

RULES:
- Call the tool only ONCE per URL.
- If the page returns blocked content, a CAPTCHA page, or no price: state
  "Price not found — page may be blocked" — do NOT guess prices.
- Report the exact price string as it appears on the page.
- Always include the source URL in your output citations.

Only output JSON. Follow the JSON schema below. Do not output anything else.
I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""


def init_brightdata_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="BrightDataFetcherAgent",
        instructions=INSTRUCTIONS,
        tools=[brightdata_fetch],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None,
    )
