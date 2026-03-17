"""Extract legal issues/questions addressed in the judgment."""

from typing import List

from pydantic import BaseModel, Field

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output

from ..models import LegalIssue


class IssuesOutput(BaseModel):
    """Output: list of legal issues."""
    issues: List[LegalIssue] = Field(default_factory=list)


INSTRUCTIONS = """
You are a legal editor. Identify the key legal issues (questions) that the court addressed in this judgment.

For each issue:
- issue_text: The legal question in clear, concise form (e.g., "Whether delay in FIR affects prosecution credibility")
- supporting_paragraphs: List of paragraph numbers where this issue is discussed (if available; use empty list if not)

Output valid JSON: { "issues": [ { "issue_text": "...", "supporting_paragraphs": [] }, ... ] }
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="IssueDetectionAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=IssuesOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(IssuesOutput) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_issue_detection(text: str, config: LLMConfig) -> List[LegalIssue]:
    """Extract legal issues from judgment text."""
    agent = _init_agent(config)
    result = await ResearchRunner.run(agent, text[:15000])
    out = result.final_output_as(IssuesOutput)
    return out.issues
