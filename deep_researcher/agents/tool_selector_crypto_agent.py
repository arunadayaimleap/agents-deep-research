"""
Tool selector for crypto trading signal research.
"""

from datetime import datetime

from pydantic import BaseModel, Field
from typing import List, Optional

from ..llm_config import LLMConfig, model_supports_structured_output
from .baseclass import ResearchAgent
from .tool_selector_agent import AgentSelectionPlan, AgentTask
from .utils.parse_output import create_type_parser


INSTRUCTIONS = f"""
You decide which agents should address a knowledge gap in a **crypto catalyst research** project.
BACKGROUND CONTEXT includes a FINAL Binance snapshot (prices/scores/levels) — do NOT call MarketDataAgent unless verifying a symbol error.

AVAILABLE AGENTS:
- WebSearchAgent: Web search for catalysts, news, sentiment (PRIMARY)
- SiteCrawlerAgent: Crawl a specific news URL (requires entity_website)
- MarketDataAgent: ONLY if snapshot missing or symbol validation failed

STRATEGY:
1. For each ranked coin in the snapshot, search: "<SYMBOL> crypto news today {datetime.now().strftime('%Y-%m-%d')}"
2. Search macro catalysts: "crypto market news today", "bitcoin ETF flows", regulatory headlines
3. Use SiteCrawler on a strong article URL when snippets lack detail

GUIDELINES:
- Prefer WebSearchAgent; avoid MarketDataAgent when snapshot is present.
- Up to 3 agent tasks per plan.
- Do not repeat failed queries.

Output ONLY valid JSON matching this schema:
{AgentSelectionPlan.model_json_schema()}
"""


def init_tool_selector_crypto_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.reasoning_model
    return ResearchAgent(
        name="ToolSelectorAgent",
        instructions=INSTRUCTIONS,
        model=selected_model,
        output_type=AgentSelectionPlan if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(AgentSelectionPlan)
        if not model_supports_structured_output(selected_model)
        else None,
    )
