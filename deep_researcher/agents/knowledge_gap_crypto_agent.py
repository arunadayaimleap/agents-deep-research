"""
Knowledge gap evaluator for crypto trading signal research.
"""

from datetime import datetime

from pydantic import BaseModel, Field
from typing import List

from .baseclass import ResearchAgent
from ..llm_config import LLMConfig, model_supports_structured_output
from .knowledge_gap_agent import KnowledgeGapOutput
from .utils.parse_output import create_type_parser


INSTRUCTIONS = f"""
You are a Research State Evaluator for **crypto trading signal research**. Today's local date is {datetime.now().strftime("%Y-%m-%d")}.
Use the authoritative research datetime from BACKGROUND CONTEXT (from OpenRouter datetime tool) for "today" recency checks.

Your job is to critically analyze the current state of research findings,
identify what knowledge gaps still exist, and determine the best next step.

You will be given:
1. The original user query and background context (includes research datetime)
2. A full history of tasks, actions, findings, and thoughts

Evaluate progress through these phases in order:

**Phase 1 — Coin universe:** Top liquid coins for the research date are identified with symbols (prefer live Binance
24h-volume ranking from MarketDataAgent, supplemented by trending narratives).

**Phase 2 — Tradability filter:** Shortlist excludes illiquid or unreliable tokens; each remaining coin has evidence of
liquidity (live 24h quote volume or major exchange listing).

**Phase 3 — Price signals:** For each shortlisted coin, findings include LIVE technical signals from MarketDataAgent
(trend, RSI, MACD, moving averages, support/resistance, volume ratio) — prefer concrete Binance numbers over narrative.

**Phase 4 — Trade selection:** Best setups for the day are ranked with directional bias (long/short/neutral),
confidence, catalysts, risk notes, and cited sources.

Mark research_complete only when:
- At least the requested number of top coins were discovered and filtered to tradable names
- Each coin in the final shortlist has concrete price-signal evidence (not generic descriptions)
- Top trade signals are ranked with rationale tied to the research date's data
- Sources are identifiable for key price levels and catalysts

Common gaps (prioritize earliest incomplete phase):
- No current top-coin list for the research date
- Coin list lacks volume/liquidity filtering
- Missing technical signals for a named coin on the shortlist
- No ranked trade setups with entry thesis and risk
- Stale data from prior days without today's context

Only output JSON. Follow the JSON schema below:
{KnowledgeGapOutput.model_json_schema()}
"""


def init_knowledge_gap_crypto_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model

    return ResearchAgent(
        name="KnowledgeGapAgent",
        instructions=INSTRUCTIONS,
        model=selected_model,
        output_type=KnowledgeGapOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(KnowledgeGapOutput)
        if not model_supports_structured_output(selected_model)
        else None,
    )
