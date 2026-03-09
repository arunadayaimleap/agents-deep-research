"""
Agent used to perform web searches and summarize the results.

The SearchAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple query string as input

The Agent then:
1. Uses the web_search tool to retrieve search results
2. Analyzes the retrieved information
3. Writes a summary with citations/URLs
4. Returns the formatted summary as JSON
"""

from agents import WebSearchTool
from ...tools.web_search import create_web_search_tool
from ...tools.sendgrid_tools import send_validation_email, check_pattern_validation_status, test_email_pattern
from ...llm_config import LLMConfig, model_supports_structured_output, get_base_url
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = f"""You are a research assistant that performs web searches and provides summaries.

AVAILABLE TOOLS:
1. web_search - Search for information using natural language queries
2. send_validation_email - Send a test email to validate a REAL email address you discovered
3. test_email_pattern - Test a discovered email pattern with REAL test addresses from that organization
4. check_pattern_validation_status - Check delivery status of sent emails

WORKFLOW:
1. Use web_search to find information about the topic
2. Analyze the results and write a comprehensive summary
3. If you discover REAL email addresses (from websites, directories, signatures, etc.), validate them using SendGrid tools
4. Include all findings and any validation results in your output

IMPORTANT:
- Include citations [URL] for all information sources
- ONLY use SendGrid tools for REAL email addresses you actually discovered
- Do NOT test hypothetical or made-up email patterns like firstname.lastname@company.com
- Always output valid JSON following this schema:

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

    # SendGrid tools for email pattern validation
    tools = [web_search_tool]
    
    # Add SendGrid tools if API key is configured
    import os
    if os.getenv("SENDGRID_API_KEY"):
        tools.extend([
            send_validation_email,
            check_pattern_validation_status,
            test_email_pattern,
        ])

    return ResearchAgent(
        name="WebSearchAgent",
        instructions=INSTRUCTIONS,
        tools=tools,
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None
    )
