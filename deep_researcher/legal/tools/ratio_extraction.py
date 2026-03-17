"""Extract the ratio decidendi (binding legal principle) from the judgment."""

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output

from ..models import RatioDecidendi


INSTRUCTIONS = """
You are a legal editor. Identify the ratio decidendi (binding legal principle) of this judgment.

The ratio is the rule of law that is necessary to decide the case and that binds lower courts.
- ratio: One or two clear sentences stating the binding principle
- supporting_paragraphs: Paragraph numbers where the ratio is stated or applied (if available)

Output valid JSON: { "ratio": "...", "supporting_paragraphs": [41, 42] }
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="RatioExtractionAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=RatioDecidendi if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(RatioDecidendi) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_ratio_extraction(text: str, config: LLMConfig) -> RatioDecidendi:
    """Extract ratio decidendi from judgment text."""
    agent = _init_agent(config)
    result = await ResearchRunner.run(agent, text[:15000])
    return result.final_output_as(RatioDecidendi)
