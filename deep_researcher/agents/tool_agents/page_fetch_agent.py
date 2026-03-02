"""
Agent that fetches the full rendered content of a specific product or web page
using the Jina Reader API tool, then extracts and summarizes relevant information.

Use this agent when you have a direct URL and need to read its actual content —
especially for JavaScript-heavy pages like Amazon, Flipkart, BestBuy, etc.
where a standard web search snippet won't contain price data.

The agent:
1. Takes a direct URL from the AgentTask (via entity_website or embedded in query)
2. Calls the fetch_page_content tool (Jina Reader) to get rendered Markdown
3. Extracts the relevant information: product name, price, availability, specs
4. Returns a structured ToolAgentOutput with citations
"""

from ...tools.jina_reader import fetch_page_content
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


INSTRUCTIONS = f"""You are a page content extraction agent. You fetch the full rendered content
of a specific web page and extract structured information from it.

OBJECTIVE:
Given an AgentTask, follow these steps:
1. Identify the target URL from the 'entity_website' field or extract it from the 'query' field.
2. Call the fetch_page_content tool with that URL to retrieve the page content.
3. From the returned content, extract and summarize the following (where available):
   - Product name / title
   - Price (with currency symbol)
   - Stock / availability status
   - Key product specifications (model number, storage, color, etc.)
   - Seller / fulfilled by information
4. Write a concise summary of your findings with the source URL cited.

GUIDELINES:
- Use the EXACT URL provided — do not modify or guess URLs.
- If the page returns an error or irrelevant content, state "Could not retrieve content from [URL]".
- Only call the tool ONCE per URL.
- Always include the source URL in your output citations.
- Be precise about prices — include the exact currency symbol and amount as shown on the page.
- If a price is not found on the page, explicitly state "Price not found on page".

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
