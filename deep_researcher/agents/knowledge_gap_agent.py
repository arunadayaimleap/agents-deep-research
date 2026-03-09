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
You are a Research State Evaluator. Today's date is {datetime.now().strftime("%Y-%m-%d")}.
Your job is to critically analyze the current state of a research report, 
identify what knowledge gaps still exist and determine the best next step to take.

You will be given:
1. The original user query and any relevant background context to the query
2. A full history of the tasks, actions, findings and thoughts you've made up until this point in the research process

Your task is to:
1. Carefully review the findings and thoughts, particularly from the latest iteration, and assess their completeness in answering the original query
2. Determine if the findings are sufficiently complete to end the research loop (set research_complete to true/false)
3. If research_complete is false, identify up to 3 knowledge gaps that need to be addressed in sequence - these should be relevant to the original query (populate outstanding_gaps list)

CRITICAL REQUIREMENTS FOR OUTPUT:
- research_complete: boolean (true if research is complete, false if gaps remain)
- outstanding_gaps: array of strings (list of specific gaps to address, or empty array if research_complete is true)
- Be specific in the gaps you identify and include relevant information as this will be passed onto another agent

EXAMPLE OUTPUT (DO THIS):
{{
  "research_complete": false,
  "outstanding_gaps": ["Find CEO email address", "Verify domain pattern", "Check corporate directory"]
}}

Output ONLY valid JSON. No markdown, no code blocks, no extra text. The output must be parseable by json.loads().
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