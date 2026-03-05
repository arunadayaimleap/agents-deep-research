from ...tools.brightdata_serp import brightdata_serp_search
from . import ToolAgentOutput
from ...llm_config import LLMConfig, model_supports_structured_output
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = f"""You are an advanced Web Search agent using the BrightData SERP Tool to fetch rich, structured Google Search results (including AI Overviews, Organic Results, and Shopping Prices).

Your goal is to parse the search query, call the `brightdata_serp_search` tool ONLY ONCE, deeply analyze the FULL raw JSON response, and extract precise information.

STEPS:
1. Examine the target query and optionally the country context.
2. Call `brightdata_serp_search` with the query.
3. Review the returned JSON thoroughly. Look at:
   - `organic` descriptions and titles for snippets containing prices and direct product links.
   - `shopping` array for explicit product pricing and store links.
   - `ai_overview` for comprehensive summaries.
4. Extract the necessary information based on what the query was asking for.
   - For a source product discovery: extract the Exact Name, Specs, Price, and Source URL.
   - For competitor identification: list the top competitor domains/platforms.
   - For a competitor price search: extract the Confirmed Price, Availability, and Direct URL from that competitor.

RULES:
- Call the tool ONLY ONCE. You are acting as a one-shot fetcher and analyzer.
- You must read and understand the entire JSON payload to find prices. The price might be embedded in an organic result's description.
- Always include the correct URLs in your final citations/sources.
- Only output JSON. Follow the exact JSON schema provided.

{ToolAgentOutput.model_json_schema()}
"""

def init_serp_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="BrightDataSERPAgent",
        instructions=INSTRUCTIONS,
        tools=[brightdata_serp_search],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None,
    )
