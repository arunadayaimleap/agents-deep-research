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
You are a Research State Evaluator for **crypto catalyst research**. Today's local date is {datetime.now().strftime("%Y-%m-%d")}.

BACKGROUND CONTEXT includes an **AUTHORITATIVE BINANCE MARKET SNAPSHOT** — prices, scores, RSI, MACD, levels, and rankings are FINAL.
Do NOT require additional MarketDataAgent work for technicals or ranking.

Your job: check whether **news catalysts** exist for each ranked coin in the snapshot.

Mark research_complete when:
- Each ranked coin has at least one dated news/event catalyst from the research date (or last 24–48h)
- Executive-summary-level macro context is available (optional but preferred)

Common gaps:
- Missing catalyst search for a specific symbol in the snapshot
- Only generic market commentary, no coin-specific news
- Stale news from prior weeks without today's relevance

Do NOT gap on: missing prices, RSI, scores, tradability, or trade ranking — those are pre-computed.

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
