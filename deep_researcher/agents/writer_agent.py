"""
Agent used to synthesize a final report based on provided findings.

The WriterAgent takes as input a string in the following format:
===========================================================
QUERY: <original user query>

FINDINGS: <findings from the iterative research process>
===========================================================

The Agent then:
1. Generates a comprehensive markdown report based on all available information
2. Includes proper citations for sources in the format [1], [2], etc.
3. Returns a string containing the markdown formatted report
"""
from .baseclass import ResearchAgent
from ..llm_config import LLMConfig
from datetime import datetime

INSTRUCTIONS = f"""
Write the final research report based on findings.

When FINDINGS are labeled as an evidence brief, they are already deduplicated — use them as the factual spine;
ground every concrete claim (dates, case numbers, names, holdings) in that material.

TASK:
1. Answer the original query comprehensively
2. Use markdown format
3. Include numbered citations [1], [2], etc.
4. Add a References section with URLs at the end

Be thorough, direct, and cite all sources.
"""

def init_writer_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.main_model

    return ResearchAgent(
        name="WriterAgent",
        instructions=INSTRUCTIONS,
        model=selected_model,
    )
