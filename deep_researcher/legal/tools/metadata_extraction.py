"""Extract case metadata (name, court, bench, date) from judgment text."""

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output

from ..models import CaseMetadata


INSTRUCTIONS = """
You are a legal editor. Extract case metadata from the judgment text.

EXTRACT:
- case_name: Standardized format "Plaintiff v Defendant" (e.g., State of Bihar v XYZ)
- court: Full court name (e.g., Supreme Court of India, High Court of Delhi)
- bench: Names of judges (e.g., Justice A, Justice B)
- date: Date of judgment in YYYY-MM-DD format if possible
- citation_string: Official citation if present (e.g., (2023) 5 SCC 100)

Use only information explicitly stated in the text. If a field is not found, omit it or use null.
Output valid JSON matching the CaseMetadata schema.
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="MetadataExtractionAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=CaseMetadata if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(CaseMetadata) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_metadata_extraction(text: str, config: LLMConfig) -> CaseMetadata:
    """Extract case metadata from judgment text."""
    agent = _init_agent(config)
    result = await ResearchRunner.run(agent, text[:15000])
    return result.final_output_as(CaseMetadata)
