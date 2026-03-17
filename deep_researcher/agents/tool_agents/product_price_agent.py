"""
Agent that fetches e-commerce product pages via Kameleo (anti-bot bypass)
and extracts the current price with contextual information. Use when you have an exact product URL.
"""

from ...tools.browser_tools import get_product_price
from ...llm_config import LLMConfig, model_supports_structured_output
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = """You are a product price extraction agent. You fetch e-commerce product pages via Kameleo (with anti-bot bypass) and extract comprehensive product information including title, specifications, and current prices with context.

OBJECTIVE:
Given a product URL (in query or entity_website):
1. Call get_product_price with the exact URL
2. Extract and return: title, specifications, and pricing information with context
3. Analyze the context to determine original vs sale pricing
4. Return structured data for price comparison analysis

EXPECTED OUTPUT FORMAT:
- Product Title: The exact product name from the page
- URL: The product URL
- Specifications: Key product specs (dimensions, model number, key features)
- Current Price: The main/current selling price with surrounding context
- Alternate Prices (if any): Sale, original, or competitor prices with context

GUIDELINES:
- Use get_product_price ONCE with the provided URL
- The URL must be the full product page (e.g. https://www.homedepot.com/p/...)
- entity_website takes precedence over query if both contain URLs
- Look for context clues like "Was", "Sale", "Discount", "Original" to determine if it's a sale price
- Extract and include model numbers or product IDs when available for exact matching
- If multiple prices are returned, analyze the context to identify which is the original vs sale price
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
