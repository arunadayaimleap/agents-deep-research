"""
Agent used to evaluate the state of the research report (typically done in a loop) and identify
knowledge gaps that still need to be addressed.

For MRO research, when research is complete it also returns a list of related aircraft/engine
configurations that should be queued for follow-up research (same engine family, sibling
variants, competing OEMs, high-signal subcomponents).

Input format:
===========================================================
ORIGINAL QUERY: <original user query>

HISTORY OF ACTIONS, FINDINGS AND THOUGHTS: <breakdown of activities and findings so far>
===========================================================

The Agent:
1. Reviews current findings and assesses completeness
2. Identifies up to 3 specific knowledge gaps still needed
3. When complete, extracts up to 5 related MRO targets for the research queue
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from .utils.parse_output import create_type_parser


class MRORelatedTarget(BaseModel):
    """A related aircraft/engine/part configuration worth researching next."""
    aircraft: str = Field(description="Aircraft model, e.g. 'Airbus A320ceo'")
    part: str = Field(description="Part type, e.g. 'engine', 'landing gear', 'APU'")
    make: Optional[str] = Field(
        default=None,
        description="Specific make/model if determinable from findings, e.g. 'CFM56-5B', 'V2500-A5'"
    )
    relationship: str = Field(
        description=(
            "Why this target is related to the current research. One of: "
            "SAME_ENGINE_FAMILY | SIBLING_AIRCRAFT_VARIANT | COMPETING_OEM | "
            "SUBCOMPONENT_DEEP_DIVE | SHARED_OPERATOR_FLEET | REGULATORY_SPILLOVER"
        )
    )
    reason: str = Field(
        description="1-2 sentence explanation of why this configuration is relevant and what to investigate."
    )
    priority: str = Field(
        default="medium",
        description="Research priority relative to the completed report: high | medium | low"
    )


class KnowledgeGapOutput(BaseModel):
    """Output from the Knowledge Gap Agent"""
    research_complete: bool = Field(
        description="Whether the research and findings are complete enough to end the research loop"
    )
    outstanding_gaps: List[str] = Field(
        description="List of knowledge gaps that still need to be addressed (up to 3). Empty when complete."
    )
    related_mro_targets: List[MRORelatedTarget] = Field(
        default_factory=list,
        description=(
            "Populated ONLY when research_complete=True. "
            "List of up to 5 related MRO configurations to add to the research queue. "
            "Derive these from the findings: sibling engine variants, competing OEMs on the same "
            "airframe, high-signal subcomponents, aircraft variants sharing the same engine family, "
            "or fleets cited in incident/AD patterns. Leave empty when research is NOT complete."
        )
    )


INSTRUCTIONS = f"""
You are an MRO (Maintenance, Repair, Overhaul) research evaluator. Assess research completeness
and identify knowledge gaps or related follow-up targets.

TASK:
1. Review the MRO research findings so far for the aircraft/engine/part configuration.
2. Decide if research_complete should be true or false.
   - Set true only when ALL of the following are covered with at least 2 credible sources each:
     * Compatibility validation
     * Fleet exposure (size, age, operators)
     * Incident/SDR signals (FAA, EASA, NTSB)
     * Regulatory directives (ADs, service bulletins)
     * Module-level or subcomponent-level opportunity ranking
   - Set false if any category is missing or unsupported.
3. If NOT complete: list up to 3 specific knowledge gaps still needed.
4. If complete: populate related_mro_targets with up to 5 related configurations to research next.
   Derive targets from actual entities mentioned in the findings:
   - Engine family siblings (e.g., CFM56-7B → CFM56-7B27, CFM56-7BE)
   - Aircraft variants sharing the same engine (e.g., 737-800 → 737-700, 737-900ER)
   - Competing OEM on the same airframe (e.g., A320 CFM56-5B → A320 V2500-A5)
   - High-opportunity subcomponents named in the findings (e.g., HPT blades → HPC stages)
   - Operators or fleets cited with elevated incident/AD exposure

OUTPUT FORMAT (valid JSON only):
{{
  "research_complete": boolean,
  "outstanding_gaps": ["gap 1", "gap 2"],
  "related_mro_targets": [
    {{
      "aircraft": "...",
      "part": "...",
      "make": "..." or null,
      "relationship": "SAME_ENGINE_FAMILY",
      "reason": "...",
      "priority": "high"
    }}
  ]
}}

Schema:
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
