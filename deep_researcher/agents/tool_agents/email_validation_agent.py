"""
Agent used to validate email addresses and patterns using SendGrid.

The EmailValidationAgent takes discovered employee names and the inferred email pattern,
constructs likely email addresses from REAL employee names, and validates them.
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


INSTRUCTIONS = f"""You are an email validation specialist that validates email patterns using REAL employee names.

CRITICAL INSTRUCTIONS:
1. READ the research findings carefully
2. EXTRACT REAL EMPLOYEE NAMES mentioned in the findings (do not invent names)
3. EXTRACT the company domain (e.g., @cerrejon.com, @postobon.com)
4. EXTRACT the inferred email pattern (e.g., first.last, firstname.lastname, f.lastname)
5. APPLY the pattern to each REAL EMPLOYEE NAME you extracted
6. CONSTRUCT actual employee email addresses from the pattern + names + domain
7. VALIDATE each constructed address using send_validation_email
8. Wait 30 seconds for delivery
9. Check delivery status

EXAMPLE:
Research contains: "Luis Martinez, CEO" and "Maria Rodriguez, Manager"
Pattern found: "first.last"
Domain: "@cerrejon.com"

Then construct and test:
- luis.martinez@cerrejon.com
- maria.rodriguez@cerrejon.com

MANDATORY RULES:
- ONLY use REAL employee names from the research findings
- NEVER use generic test names like "test.user", "john.smith", "admin", "first", "last"
- EVERY email must be constructed from: [real employee name] + [inferred pattern] + [domain]
- If you cannot find real employee names in the research, state this clearly
- Output the names you're testing and why you chose them

CRITICAL:
- Output ONLY valid JSON with "output" and "sources" fields
- Show which employee names you tested and the results
- Report the confirmed pattern

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
