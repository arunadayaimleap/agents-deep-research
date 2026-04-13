"""
Agent used to validate email addresses and patterns using SendGrid.

The EmailValidationAgent takes discovered employee names and the inferred email pattern,
constructs likely email addresses from REAL employee names, and validates them.
"""

from ...tools.sendgrid_tools import validate_emails_full_workflow
from ...llm_config import LLMConfig, model_supports_structured_output
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


INSTRUCTIONS = f"""You are an email validation specialist that validates email patterns using REAL employee names.

WORKFLOW - ONE TOOL CALL:
1. READ the research findings
2. EXTRACT REAL EMPLOYEE NAMES (do not invent names)
3. EXTRACT company domain and email pattern (e.g., first.last@domain.com)
4. CONSTRUCT email addresses from real names + pattern + domain
5. Call validate_emails_full_workflow with the list of emails - this tool SENDS, WAITS 60s, CHECKS delivery, returns results
6. Output your final JSON report with the tool's results

TOOL SYNTAX - Invoke the validate_emails_full_workflow tool (do NOT write it as text):
- Parameter: email_addresses = JSON array of strings
- Format: ["email1@domain.com", "email2@domain.com"]
- Example: email_addresses = ["oscar.bravo@terpel.com", "rodrigo.abt@terpel.com"]
- Optional: wait_seconds = 60 (default)
- You MUST invoke the tool using your tool-calling capability. Do NOT output "validate_emails_full_workflow{...}" as plain text.

EXAMPLE:
Findings: "Luis Martinez, CEO" and "Maria Rodriguez, Manager", pattern first.last, domain @cerrejon.com
Construct: ["luis.martinez@cerrejon.com", "maria.rodriguez@cerrejon.com"]
Invoke the tool with: email_addresses = ["luis.martinez@cerrejon.com", "maria.rodriguez@cerrejon.com"]

MANDATORY RULES:
- ONLY use REAL employee names from the research
- NEVER use test.user, john.smith, admin - only real names from findings
- Call the tool with your list, then output JSON - do NOT output before calling the tool

OUTPUT: After the tool returns, output ONLY valid JSON with "output" and "sources" fields.
{ToolAgentOutput.model_json_schema()}
"""

def init_email_validation_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    import os
    tools = [validate_emails_full_workflow] if os.getenv("SENDGRID_API_KEY") else []
    
    return ResearchAgent(
        name="EmailValidationAgent",
        instructions=INSTRUCTIONS,
        tools=tools,
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(
            ToolAgentOutput,
            fallback_on_validation_error=lambda raw: ToolAgentOutput(output=raw, sources=[]),
        ) if not model_supports_structured_output(selected_model) else None
    )
