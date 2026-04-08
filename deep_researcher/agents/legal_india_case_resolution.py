"""
Pre-loop case resolution for India legal article research.

Runs once on the desk brief (title, angle, seeds, working date) before any web search.
Produces a normalized anchor for the matter and a suggested first search seed — without
fabricating diary numbers or citations that are not verbatim in the input.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from .utils.parse_output import create_type_parser


class CaseResolutionOutput(BaseModel):
    """Structured result of reasoning-only case resolution from the query text."""

    resolution_status: str = Field(
        description=(
            "resolved_from_query | partial_from_query | not_found | ambiguous — "
            "resolved_from_query = clear single matter with at least one verbatim identifier OR "
            "unambiguous party+court+subject; ambiguous = two or more plausible distinct matters; "
            "not_found = insufficient to anchor a specific proceeding"
        )
    )
    confidence: str = Field(description="high | medium | low")
    canonical_matter_label: str = Field(
        default="",
        description="Short neutral label, e.g. party A v. party B (subject) before [forum]",
    )
    parties_mentioned: List[str] = Field(
        default_factory=list,
        description="Party / entity names explicitly present in the brief",
    )
    court_or_forum: str = Field(
        default="",
        description="Court, tribunal, or regulator named or clearly implied (India only)",
    )
    rough_timeframe: str = Field(
        default="",
        description="Year or date window implied by working date + angle (plain text)",
    )
    normalized_identifiers: List[str] = Field(
        default_factory=list,
        description=(
            "Official-style identifiers copied VERBATIM from the query only — "
            "diary no., SLP/WP/CA/Review numbers, CCI appeal nos., etc. Empty if none appear in text."
        ),
    )
    internal_anchor_id: str = Field(
        default="",
        description=(
            "Stable lowercase slug for this brief: forum + year + short party tokens — "
            "for disambiguation only, not a court case number. Use empty if not_found."
        ),
    )
    tool_search_seed: str = Field(
        description=(
            "One 8–18 word India-focused search line for iteration 1: combine forum, parties, "
            "identifier keywords (diary, case no, SLP), and year. Must not invent numbers."
        )
    )
    identifier_notes: str = Field(
        default="",
        description="Explain missing numbers or what tools must still discover",
    )
    disambiguation_warning: str = Field(
        default="",
        description="If ambiguous: name the competing readings; else empty",
    )


INSTRUCTIONS = """
You resolve **which concrete Indian legal matter** a news-desk brief refers to, using **ONLY** the
text in the user message (topic title, angle, seed phrases, working date). You have **no web access**.

GOALS:
1. Extract **parties**, **forum** (court / tribunal / regulator), and **time hints** visible in the text.
2. List **normalized_identifiers**: every diary number, SLP/WP/CA/Review/Curative/appeal number,
   company appeal number, CCI case number, etc. that appears **verbatim** in the brief. If none appear, use [].
3. **Never invent** citations, diary numbers, or docket strings — hallucinated ids break downstream research.
4. Set **resolution_status**:
   - `resolved_from_query` — one clear matter and (verbatim identifiers OR unambiguous party+forum+subject).
   - `partial_from_query` — matter is identifiable but key official numbers are missing from the text (tools must find them).
   - `ambiguous` — the brief could plausibly describe two+ different proceedings; explain in disambiguation_warning.
   - `not_found` — the text is too vague to anchor any specific case (policy piece, generic roundup).
5. **internal_anchor_id**: slug `forum_short|year|partytoken` (ASCII, hyphens), e.g. `sci|2024|state-x-y`; use "" if not_found.
6. **tool_search_seed**: a single concrete search line for Bright Data / Google (India, English), 8–18 words,
   embedding forum + party tokens + "diary" / "case number" / "SLP" as appropriate — **no fabricated numbers**.

OUTPUT: ONE JSON object with the field names exactly as in the schema the runtime expects (data only).
Do NOT output JSON Schema, $defs, or "properties" blocks.
"""


def _case_resolution_fallback(_raw: str) -> CaseResolutionOutput:
    return CaseResolutionOutput(
        resolution_status="not_found",
        confidence="low",
        canonical_matter_label="",
        parties_mentioned=[],
        court_or_forum="",
        rough_timeframe="",
        normalized_identifiers=[],
        internal_anchor_id="",
        tool_search_seed="India site:livelaw.in site:barandbench.com legal",
        identifier_notes="Case resolution JSON failed; use generic India legal search.",
        disambiguation_warning="",
    )


def init_legal_india_case_resolution_agent(config: LLMConfig) -> ResearchAgent:
    selected = config.reasoning_model
    return ResearchAgent(
        name="LegalIndiaCaseResolutionAgent",
        instructions=INSTRUCTIONS,
        model=selected,
        output_type=CaseResolutionOutput if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(
            CaseResolutionOutput,
            fallback_on_validation_error=_case_resolution_fallback,
        )
        if not model_supports_structured_output(selected)
        else None,
    )
