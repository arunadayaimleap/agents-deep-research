"""Generate a concise research summary of the case."""

from pydantic import BaseModel, Field

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output


class CaseSummaryOutput(BaseModel):
    """Output: short summary text."""
    summary: str = Field(description="Concise 2-4 sentence research summary of the case and holding")


INSTRUCTIONS = """
You are a legal editor. Write a concise research summary of this judgment (2-4 sentences).

Include: what the case was about, the key legal issue, and the court's holding/outcome.
Do not use bullet points; write in flowing prose.
Output valid JSON: { "summary": "..." }
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="CaseSummaryAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=CaseSummaryOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(CaseSummaryOutput) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_case_summary(text: str, config: LLMConfig) -> str:
    """Generate concise case summary."""
    agent = _init_agent(config)
    result = await ResearchRunner.run(agent, text[:15000])
    out = result.final_output_as(CaseSummaryOutput)
    return out.summary
