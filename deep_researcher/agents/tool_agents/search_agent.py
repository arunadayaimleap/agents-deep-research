"""
Agent used to perform web searches and summarize the results.

The SearchAgent takes as input a string in the format of AgentTask.model_dump_json(), or can take a simple query string as input

The Agent then:
1. Uses the web_search tool to retrieve search results
2. Analyzes the retrieved information
3. Writes a 3+ paragraph summary of the search results
4. Includes citations/URLs in brackets next to information sources
5. Returns the formatted summary as a string

The agent can use either OpenAI's built-in web search capability or a custom
web search implementation based on environment configuration.

If email addresses are discovered during research, the agent can use SendGrid tools
to validate email patterns by sending test emails and checking delivery status.
"""

from agents import WebSearchTool
from ...tools.web_search import create_web_search_tool
from ...tools.sendgrid_tools import send_validation_email, check_pattern_validation_status, test_email_pattern
from ...llm_config import LLMConfig, model_supports_structured_output, get_base_url
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser

INSTRUCTIONS = f"""You are a research assistant that specializes in retrieving and summarizing information from the web.

OBJECTIVE:
Given an AgentTask, follow these steps:
- You may query the web_search tool in natural language, including full questions
- If an 'entity_website' is provided, include the domain name in the search query when useful
- Enter the query into the web_search tool
- After using the web_search tool, write a 3+ paragraph summary that captures the main points from the search results

EMAIL PATTERN VALIDATION:
If your research discovers potential email addresses or email patterns:
- Use send_validation_email to test if the address is active
- Use test_email_pattern to validate a discovered pattern with multiple test addresses
- Use check_pattern_validation_status to verify delivery status of test emails
- Report which patterns were successfully validated (confirmed active emails)

GUIDELINES:
- In your summary, try to comprehensively answer/address the 'gap' provided (which is the objective of the search)
- The summary should always quote detailed facts, figures and numbers where these are available
- If the search results are not relevant to the search term or do not address the 'gap', simply write "No relevant results found"
- Use headings and bullets to organize the summary if needed
- Include citations/URLs in brackets next to all associated information in your summary
- Report any validated email patterns in a dedicated "Email Pattern Validation" section
- Do not make additional searches

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
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