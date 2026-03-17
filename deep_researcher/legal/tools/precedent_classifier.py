"""Classify how each citation is used (RELIES_ON, DISTINGUISHES, etc.)."""

from typing import List

from pydantic import BaseModel, Field

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output

from ..models import PrecedentRelationship


class ClassifiedCitation(BaseModel):
    """One citation with its relationship."""
    citation_text: str = Field(description="The citation string")
    relationship: PrecedentRelationship = Field(description="How the case is used")


class PrecedentClassificationOutput(BaseModel):
    """Output: list of citation classifications."""
    classifications: List[ClassifiedCitation] = Field(default_factory=list)


INSTRUCTIONS = """
You are a legal analyst. For each case citation in the judgment, determine HOW it is used.

RELATIONSHIPS:
- RELIES_ON: The court relies on this case as supporting authority
- FOLLOWS: The court follows the principle from this case
- DISTINGUISHES: The court distinguishes the facts or law from this case
- OVERRULES: The court overrules this case
- REFERS_TO: General reference without clear reliance or distinction
- APPLIES: The court applies the rule from this case to the facts

Given the list of citation strings and the judgment context, output a classifications array with citation_text and relationship for each.
Output valid JSON: { "classifications": [ { "citation_text": "...", "relationship": "RELIES_ON" }, ... ] }
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="PrecedentClassifierAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=PrecedentClassificationOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(PrecedentClassificationOutput) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_precedent_classifier(
    citation_texts: List[str],
    context_excerpt: str,
    config: LLMConfig,
) -> List[ClassifiedCitation]:
    """Classify each citation's relationship. Returns list of (citation_text, relationship)."""
    if not citation_texts:
        return []
    agent = _init_agent(config)
    input_str = f"Citations to classify:\n" + "\n".join(f"- {c}" for c in citation_texts)
    input_str += f"\n\nRelevant judgment context:\n{context_excerpt[:8000]}"
    result = await ResearchRunner.run(agent, input_str)
    out = result.final_output_as(PrecedentClassificationOutput)
    return out.classifications
