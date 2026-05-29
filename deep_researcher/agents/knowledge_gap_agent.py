"""
Agent used to evaluate the state of the research report (typically done in a loop) and identify knowledge gaps that still 
need to be addressed.

The Agent takes as input a string in the following format:
===========================================================
ORIGINAL QUERY: <original user query>

HISTORY OF ACTIONS, FINDINGS AND THOUGHTS: <breakdown of activities and findings carried out so far>
===========================================================

The Agent then:
1. Carefully reviews the current draft and assesses its completeness in answering the original query
2. Identifies specific knowledge gaps that still exist and need to be filled
3. Returns a KnowledgeGapOutput object
"""

from pydantic import BaseModel, Field
from typing import List
from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from datetime import datetime
from .utils.parse_output import create_type_parser

class KnowledgeGapOutput(BaseModel):
    """Output from the Knowledge Gap Agent"""
    research_complete: bool = Field(description="Whether the research and findings are complete enough to end the research loop")
    outstanding_gaps: List[str] = Field(description="List of knowledge gaps that still need to be addressed")


INSTRUCTIONS = f"""
You are a Research State Evaluator for **criminal case news research**. Today's date is {datetime.now().strftime("%Y-%m-%d")}.
Your job is to critically analyze the current state of a research report,
identify what knowledge gaps still exist and determine the best next step to take.

You will be given:
1. The original user query and any relevant background context
2. A full history of the tasks, actions, findings and thoughts from the research process

Your task is to:
1. Review findings for completeness against the query (top cases today OR a specific case briefing)
2. Determine if findings are sufficient to produce the final structured report
3. If not, identify up to 3 knowledge gaps in sequence

For crime research, common gaps include:
- Which cases are actually leading today's news (not outdated stories)
- Missing timeline dates, charges, or jurisdiction for a named case
- No official source (court, police, prosecutor) for a key claim
- Unclear status (investigation vs trial vs sentencing)
- Need to verify a disputed fact across multiple outlets

Mark research_complete only when each target case has: headline, jurisdiction, status, key parties,
charges or alleged offenses (labeled appropriately), a dated timeline, and cited sources.

Only output JSON. Follow the JSON schema below:
{KnowledgeGapOutput.model_json_schema()}
"""

def init_knowledge_gap_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="KnowledgeGapAgent",
        instructions=INSTRUCTIONS,
        model=selected_model,
        output_type=KnowledgeGapOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(KnowledgeGapOutput) if not model_supports_structured_output(selected_model) else None
    )