"""
Agent used to perform web searches and summarize the results.

The SearchAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple query string as input

The Agent then:
1. Uses the web_search tool to retrieve search results
2. Analyzes the retrieved information
3. Writes a summary with citations
4. Returns the formatted summary as JSON
"""

from agents import WebSearchTool
from ...tools.web_search import create_web_search_tool
from ...llm_config import LLMConfig, model_supports_structured_output, get_base_url
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = f"""You are a research assistant that specializes in retrieving and summarizing information from the web.

OBJECTIVE:
Given a search query:
1. Use the web_search tool ONCE with the query provided
2. Analyze the search results
3. Write a comprehensive summary of the findings
4. Include all relevant citations and URLs

GUIDELINES:
- Use the web_search tool ONLY ONCE per task
- Do NOT do multiple searches
- Do NOT modify or expand the query
- Write a thorough summary that answers the query
- Include citations [URL] for all information sources
- If results are not relevant, state that clearly
- Use headings and bullets to organize if helpful

CRITICAL:
- Output ONLY valid JSON
- Do not include any narrative, thinking, or tool invocations
- The JSON must have "output" and "sources" fields
- Do not output anything except the JSON

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
