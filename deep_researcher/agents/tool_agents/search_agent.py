"""
Agent used to perform web searches and find employee information.

The SearchAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple query string as input

The Agent then:
1. Uses the web_search tool to retrieve search results
2. Analyzes the retrieved information and looks for employee names and email addresses
3. Identifies email patterns from discovered employees
4. Returns the findings as JSON with citations
"""

from agents import WebSearchTool
from ...tools.web_search import create_web_search_tool
from ...llm_config import LLMConfig, model_supports_structured_output, get_base_url
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = f"""You are a research assistant that finds employee names and email addresses.

TOOLS AVAILABLE:
You have access to web_search. Use it to find information about the company.

YOUR TASK:
1. Search for real employee names, titles, and email addresses
2. Look for email patterns used by the company
3. Document what you find
4. Ignore generic emails like info@, contact@, hr@, support@

IMPORTANT - HOW TO RESPOND:
- Do NOT write tool names or syntax
- Do NOT output narrative or thinking
- ONLY output the final JSON result
- The JSON must have exactly two fields: "output" and "sources"

OUTPUT ONLY THIS JSON FORMAT (nothing else, no markdown, no explanation):
{{
  "output": "What you found: employee names, email addresses discovered, inferred patterns, and sources",
  "sources": ["url1", "url2", "url3"]
}}

{ToolAgentOutput.model_json_schema()}
"""

def init_search_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model
    provider_base_url = get_base_url(selected_model)

    if config.search_provider == "openai" and 'openai.com' not in provider_base_url:
        raise ValueError(f"You have set the SEARCH_PROVIDER to 'openai', but are using the model {str(selected_model.model)} which is not an OpenAI model")
    elif config.search_provider == "openai":
        web_search_tool = WebSearchTool()
    else:
        web_search_tool = create_web_search_tool(config)

    return ResearchAgent(
        name="WebSearchAgent",
        instructions=INSTRUCTIONS,
        tools=[web_search_tool],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None
    )
