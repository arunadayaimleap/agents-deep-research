"""
Agent that fetches e-commerce product pages via Playwright + BrightData proxy
and extracts the current price. Use when you have an exact product URL.
"""

from ...tools.browser_tools import get_product_price
from ...llm_config import LLMConfig, model_supports_structured_output
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = """You are a product price extraction agent. You fetch e-commerce product pages via BrightData proxy and extract the current price.

OBJECTIVE:
Given a product URL (in query or entity_website):
1. Call get_product_price with the exact URL
2. Return the extracted price and any relevant info

GUIDELINES:
- Use get_product_price ONCE with the provided URL
- The URL must be the full product page (e.g. https://www.homedepot.com/p/...)
- entity_website takes precedence over query if both contain URLs
- Output ONLY valid JSON with "output" and "sources" fields

{ToolAgentOutput.model_json_schema()}
"""


def init_product_price_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model
    return ResearchAgent(
        name="ProductPriceAgent",
        instructions=INSTRUCTIONS,
        tools=[get_product_price],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(
            ToolAgentOutput,
            fallback_on_validation_error=lambda raw: ToolAgentOutput(output=str(raw), sources=[]),
        ) if not model_supports_structured_output(selected_model) else None
    )
