"""Generate SCC-style headnotes from the judgment."""

from typing import List

from pydantic import BaseModel, Field

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output

from ..models import Headnote


class HeadnotesOutput(BaseModel):
    """Output: list of headnotes."""
    headnotes: List[Headnote] = Field(default_factory=list)


INSTRUCTIONS = """
You are a legal editor creating SCC-style headnotes.

Format: Topic chain with em dash separators, then condensed principle and outcome.
Example: "Criminal Law — Evidence — FIR — Delay — Delay explained satisfactorily — Conviction upheld."

Create 1-3 headnotes that capture the key legal principles and outcome. Each headnote:
- headnote_text: Full headnote string in the format above
- topic_chain: Optional list of topic levels, e.g. ["Criminal Law", "Evidence", "FIR Delay"]

Output valid JSON: { "headnotes": [ { "headnote_text": "...", "topic_chain": [] }, ... ] }
"""


def _init_agent(config: LLMConfig) -> ResearchAgent:
    return ResearchAgent(
        name="HeadnoteGeneratorAgent",
        instructions=INSTRUCTIONS,
        model=config.fast_model,
        output_type=HeadnotesOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(HeadnotesOutput) if not model_supports_structured_output(config.fast_model) else None,
    )


async def run_headnote_generator(text: str, config: LLMConfig) -> List[Headnote]:
    """Generate headnotes from judgment text."""
    agent = _init_agent(config)
    result = await ResearchRunner.run(agent, text[:15000])
    out = result.final_output_as(HeadnotesOutput)
    return out.headnotes
