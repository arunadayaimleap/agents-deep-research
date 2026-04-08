"""
Compresses multi-iteration tool outputs into a single deduplicated evidence brief for WriterAgent.

Uses fast_model — the final article stays on main_model only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from .utils.parse_output import create_type_parser


class EvidenceBriefOutput(BaseModel):
    brief_markdown: str = Field(
        description=(
            "Dense markdown brief: deduplicated atomic facts, each tied to source URL(s) where known; "
            "no draft article prose."
        )
    )


INSTRUCTIONS = """
You are an evidence editor for downstream report writing. You receive raw tool outputs from several
research iterations (web search, site crawl, court search). Your job is to produce ONE markdown
document: a **deduplicated evidence brief** — not an article, not a lede, not analysis.

RULES:
1. **Deduplicate**: merge near-duplicate facts and repeated URLs; keep one canonical bullet per distinct claim.
2. **Atomic bullets**: each bullet = one checkable fact or short quote; after the fact add source URLs in parentheses when available (multiple URLs separated by semicolons).
3. **Preserve verbatim**: case names, diary numbers, appeal/SLP/WP numbers, statute sections, party names, judge names, dates — copy exactly from the raw text; do not invent or normalize citations.
4. **Structure** (use these markdown headings in order):
   - ## Case / matter identifiers (numbers, courts, parties) — use `Not seen in sources` only if nothing appeared
   - ## Chronology hints (dated events only if dates appear in raw material)
   - ## Legal / regulatory content (statutes, issues, holdings as stated in sources)
   - ## Other material facts
   - ## Source index — numbered list of every distinct URL (deduped), for the writer's References section
5. **Uncertainty**: if two sources conflict, note both briefly and mark "Sources disagree".
6. **Length**: stay under ~12,000 characters if input is huge; prioritize identifiers, dates, and primary URLs over fluff.
7. **Do not** write essay paragraphs, recommendations, or "In conclusion". No `[1]` numeric citations here — URLs inline and in Source index only.

CRITICAL OUTPUT:
- Respond with ONE JSON object: {"brief_markdown": "<your brief>"}.
- Do NOT output JSON Schema, $defs, or "properties" metadata.
"""


def _fallback_brief(raw: str) -> EvidenceBriefOutput:
    return EvidenceBriefOutput(brief_markdown=raw[:120000] if raw else "(Evidence packing failed; use raw findings.)")


def init_evidence_packer_agent(config: LLMConfig) -> ResearchAgent:
    selected = config.fast_model
    return ResearchAgent(
        name="EvidencePackerAgent",
        instructions=INSTRUCTIONS,
        model=selected,
        output_type=EvidenceBriefOutput if model_supports_structured_output(selected) else None,
        output_parser=create_type_parser(
            EvidenceBriefOutput,
            fallback_on_validation_error=_fallback_brief,
        )
        if not model_supports_structured_output(selected)
        else None,
    )
