"""LLM-based text cleaning and formatting for judgment text."""

from pydantic import BaseModel, Field

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output


class CleanedTextOutput(BaseModel):
    """Output of text cleaning step."""
    cleaned_text: str = Field(description="Cleaned and formatted judgment text")


INSTRUCTIONS = """
You are an editorial assistant that cleans and standardizes raw court judgment text.

TASKS:
- Fix obvious OCR errors and typos
- Normalize paragraph breaks (one idea per paragraph where possible)
- Standardize judge names (e.g., "Hon'ble Mr. Justice X" -> "Justice X")
- Standardize case title format: "State of Bihar v XYZ" (v for versus)
- Format dates consistently (e.g., 12 May 2023)
- Do NOT add or remove legal content; only clean and format

OUTPUT: Return valid JSON with a single field "cleaned_text" containing the full cleaned judgment.
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="TextCleaningAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=CleanedTextOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(CleanedTextOutput) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_text_cleaning(raw_text: str, config: LLMConfig) -> str:
    """Clean and format judgment text. Returns cleaned text string."""
    agent = _init_agent(config)
    result = await ResearchRunner.run(agent, raw_text)
    out = result.final_output
    if isinstance(out, CleanedTextOutput):
        return out.cleaned_text
    return str(out)
