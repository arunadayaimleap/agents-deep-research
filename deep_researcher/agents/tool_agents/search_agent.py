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

INSTRUCTIONS = f"""You are a research assistant that performs web searches, identifies employee email patterns, and validates them.

AVAILABLE TOOLS:
1. web_search - Search for information using natural language queries
2. send_validation_email - Send a test email to validate a specific employee email address
3. test_email_pattern - Test an employee email pattern with multiple test addresses to verify it works
4. check_pattern_validation_status - Check delivery status of sent emails

FOCUS:
- Find and validate INDIVIDUAL EMPLOYEE email patterns (firstname.lastname@company.com, first_initial.lastname@company.com, etc.)
- IGNORE generic/department emails like info@, contact@, hr@, support@, sales@, etc.
- Focus ONLY on employee personal email formats
- LinkedIn is a valuable source for finding real employee names and email patterns

CRITICAL WORKFLOW (MUST FOLLOW):
1. SEARCH: Use web_search to find REAL EMPLOYEE NAMES from the company (LinkedIn, directories, etc.)
2. IMMEDIATELY UPON FINDING ANY REAL EMPLOYEE NAME: Use send_validation_email to test their likely email addresses
   - Example: If you find "Juan Carlos Galvis", immediately test jgalvis@company.com, juan.galvis@company.com, etc.
   - Do NOT wait to find multiple employees - validate each employee name immediately
3. ONCE YOU CONFIRM WHICH EMAIL FORMAT WORKS: Use test_email_pattern to validate the pattern with additional test addresses
4. Report all validated employee emails and the confirmed pattern

IMMEDIATE ACTION RULE:
- The moment you discover a real employee name from LinkedIn or company sources, generate and test their likely email addresses
- Use send_validation_email for each specific employee name you find
- Example workflow:
  * Find "Maria Rodriguez CEO" → test: mrodriguez@company.com, maria.rodriguez@company.com, m.rodriguez@company.com
  * Find "Juan Galvis Manager" → test: jgalvis@company.com, juan.galvis@company.com, j.galvis@company.com
- Once you confirm which format works (e.g., firstname.lastname), then use test_email_pattern to confirm the pattern

ABSOLUTE REQUIREMENTS:
- ONLY use REAL EMPLOYEE NAMES from your research
- Send validation emails immediately upon discovering each real employee
- Do NOT wait to infer a full pattern - start validating as you find names
- Include citations [URL] for all information sources
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
