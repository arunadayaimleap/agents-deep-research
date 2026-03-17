"""Map the case to a legal taxonomy (hierarchical topic classification)."""

from typing import List

from pydantic import BaseModel, Field

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output

from ..models import TaxonomyTag


class TaxonomyOutput(BaseModel):
    """Output: list of taxonomy paths."""
    tags: List[TaxonomyTag] = Field(default_factory=list)


INSTRUCTIONS = """
You are a legal classifier. Assign this judgment to nodes in a legal taxonomy.

Use a hierarchical path from broad to specific, e.g.:
- ["Criminal Law", "Evidence", "Dying Declaration", "Reliability"]
- ["Constitutional Law", "Fundamental Rights", "Article 21"]

Provide 1-3 taxonomy tags (paths). Each tag has "path": list of strings from root to leaf.
Output valid JSON: { "tags": [ { "path": ["Criminal Law", "Evidence", "FIR Delay"] }, ... ] }
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="TaxonomyClassifierAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=TaxonomyOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(TaxonomyOutput) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_taxonomy_classifier(text: str, config: LLMConfig) -> List[TaxonomyTag]:
    """Classify judgment into legal taxonomy."""
    agent = _init_agent(config)
    result = await ResearchRunner.run(agent, text[:12000])
    out = result.final_output_as(TaxonomyOutput)
    return out.tags
