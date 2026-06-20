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
You decide which agents should address a knowledge gap in a **crypto trading signal** research project.
Use the research datetime from BACKGROUND CONTEXT when queries need "today" freshness.

AVAILABLE AGENTS:
- MarketDataAgent: **LIVE Binance Spot data** — top coins by 24h volume, current price/volume, and computed
  technical signals (trend, RSI, MACD, SMAs, support/resistance, volume ratio). PREFER THIS for any hard numbers.
- WebSearchAgent: Web search for catalysts, news, sentiment, and context (call with different queries)
- SiteCrawlerAgent: Crawl a specific market data or news site (requires entity_website URL)

CRYPTO TRADING RESEARCH STRATEGY (follow this order across iterations):

1. **Discover top coins today**
   - Use MarketDataAgent with a query like "top coins by 24h volume" to get the live liquid universe from Binance.
   - Optionally cross-check trending narratives via WebSearchAgent ("crypto trending coins today").

2. **Filter reliable tradable coins**
   - MarketDataAgent top_coins already reflects liquidity (24h quote volume). Keep high-volume names;
     exclude micro-caps and obvious memecoin pumps unless explicitly requested.

3. **Study price signals per shortlisted coin**
   - For each shortlisted symbol, use MarketDataAgent to get live technical signals (trend, RSI, MACD,
     moving averages, support/resistance, volume ratio) — phrase the query as "signals for BTC" / "BTCUSDT 4h signals".
   - Use WebSearchAgent for catalysts: news, ETF flows, upgrades, regulatory headlines for the research date.

4. **Rank trade setups**
   - Combine live Binance signals with catalyst context to rank the best setups.
   - Use WebSearchAgent for analyst consensus only after per-coin signal data exists.

5. **SiteCrawler**
   - Use on a known URL when you need narrative depth not covered by market data or search snippets.

GUIDELINES:
- Prefer MarketDataAgent for prices, volume, and indicators; prefer WebSearchAgent for news/catalysts/sentiment.
- Always express coins to MarketDataAgent as symbols (BTC, ETH) — it will map to Binance pairs (BTCUSDT).
- Do not repeat failed queries from history.
- Up to 3 agent tasks per plan.
- This is research, not financial advice — gather public market data and cited analysis only.

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
