"""
Agent used to validate email addresses and patterns using SendGrid.

The EmailValidationAgent takes email addresses or patterns and validates them
by sending test emails and checking delivery status.
"""

import asyncio
from agents import function_tool
from ...tools.sendgrid_tools import send_validation_email, check_pattern_validation_status, test_email_pattern
from ...llm_config import LLMConfig, model_supports_structured_output
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


@function_tool
async def wait_seconds(seconds: int = 30) -> str:
    """Wait for a specified number of seconds before proceeding.
    
    Useful for waiting for email delivery after sending test emails.
    
    Args:
        seconds: Number of seconds to wait (default: 30)
        
    Returns:
        Confirmation message with elapsed time
    """
    print(f"[VALIDATION] Waiting {seconds} seconds for email delivery...")
    await asyncio.sleep(seconds)
    print(f"[VALIDATION] Wait complete. Checking delivery status now...")
    return f"Waited {seconds} seconds. Ready to check delivery status."


INSTRUCTIONS = f"""You are an email validation specialist that verifies email addresses and patterns.

AVAILABLE TOOLS:
1. send_validation_email - Send a test email to validate a specific email address
2. test_email_pattern - Test an email pattern with multiple test addresses
3. check_pattern_validation_status - Check delivery status of sent emails
4. wait_seconds - Wait for email delivery (recommended: 30 seconds before checking status)

FOCUS:
- Validate individual employee email addresses
- Test discovered email patterns to confirm they work
- Always wait for delivery before checking status
- Report which emails actually work and which don't

CRITICAL WORKFLOW (MUST FOLLOW):
1. SEND: Use send_validation_email for specific emails OR test_email_pattern for patterns
2. WAIT: Use wait_seconds to allow ~30 seconds for email delivery to servers
3. CHECK: After waiting, use check_pattern_validation_status to verify which emails delivered successfully
4. ANALYZE: Report which format works based on delivery results
5. OUTPUT: Include all tested addresses and their delivery status in your JSON output

ABSOLUTE REQUIREMENTS:
- ALWAYS wait using wait_seconds after sending emails before checking status
- Do NOT skip the wait step - delivery takes time
- Report delivery status for every email tested
- Indicate which addresses/patterns succeeded vs. failed
- Include all relevant sources and details in the output
- Output ONLY valid JSON in final response:

{{
  "output": "Validation results: emails tested, delivery status (success/failed), confirmed working pattern, examples",
  "sources": ["email_domain_or_source"]
}}

{ToolAgentOutput.model_json_schema()}
"""

def init_email_validation_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model
    
    # Build tools list
    tools = [wait_seconds]
    
    # Add SendGrid tools if API key is configured
    import os
    if os.getenv("SENDGRID_API_KEY"):
        tools.extend([
            send_validation_email,
            check_pattern_validation_status,
            test_email_pattern,
        ])
    
    return ResearchAgent(
        name="EmailValidationAgent",
        instructions=INSTRUCTIONS,
        tools=tools,
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None
    )
