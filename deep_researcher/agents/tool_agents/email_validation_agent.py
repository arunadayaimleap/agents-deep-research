"""
Agent used to validate email addresses and patterns using SendGrid.

The EmailValidationAgent takes discovered email addresses and validates them
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

OBJECTIVE:
Given a list of email addresses to validate:
1. For each real employee email found, use send_validation_email to test it
2. Use wait_seconds to wait 30 seconds for delivery
3. Use check_pattern_validation_status to verify delivery
4. Report which emails were successfully validated
5. Summarize the confirmed email pattern

GUIDELINES:
- ONLY validate REAL employee emails discovered in research
- NEVER test fake/test addresses like test.user@, john.smith@, admin@
- Use actual employee names and emails from the research findings
- Send emails, wait, then check status
- Report delivery results

CRITICAL:
- Output ONLY valid JSON
- Do not include tool invocations in your output
- Do not include narrative or thinking
- The JSON must have "output" and "sources" fields
- Only output the JSON

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
