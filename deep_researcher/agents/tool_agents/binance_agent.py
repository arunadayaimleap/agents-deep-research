"""
Agent that pulls live Binance Spot market data (prices, volume, technical signals)
and summarizes it for crypto trade-signal research.

Input: AgentTask.model_dump_json() (or a plain instruction string).
The agent calls the ``binance_market_data`` tool one or more times, then writes a
concise data-grounded summary with concrete numbers and the source endpoint.
"""

import json

from agents import function_tool

from ...llm_config import LLMConfig, model_supports_structured_output
from ...tools.binance_tools import (
    get_24hr,
    get_price_signals,
    get_top_symbols,
)
from . import ToolAgentOutput
from ..baseclass import ResearchAgent
from ..utils.parse_output import create_type_parser


@function_tool
async def binance_market_data(
    action: str,
    symbol: str = "",
    interval: str = "1d",
    limit: int = 15,
    quote: str = "USDT",
) -> str:
    """Fetch live Binance Spot market data.

    Args:
        action: One of "top_coins", "ticker", "signals".
            - "top_coins": top tradable coins by 24h quote volume (liquidity proxy).
            - "ticker": 24h price/volume stats for one `symbol`.
            - "signals": technical signals (trend, RSI, MACD, SMAs, support/resistance, volume) for one `symbol`.
        symbol: Trading pair, e.g. "BTCUSDT" (required for "ticker" and "signals").
        interval: Kline interval for "signals" (e.g. "1h", "4h", "1d"). Default "1d".
        limit: For "top_coins", number of coins; for "signals", number of candles. Default 15.
        quote: Quote asset for "top_coins" (default "USDT").

    Returns:
        JSON string with the requested market data.
    """
    try:
        action = (action or "").strip().lower()
        if action == "top_coins":
            data = await get_top_symbols(quote=quote, limit=limit or 15)
            return json.dumps({"action": action, "source": "binance:/api/v3/ticker/24hr", "data": data})
        if action == "ticker":
            if not symbol:
                return json.dumps({"error": "symbol is required for action 'ticker'"})
            data = await get_24hr(symbol)
            return json.dumps({"action": action, "source": f"binance:/api/v3/ticker/24hr?symbol={symbol.upper()}", "data": data})
        if action == "signals":
            if not symbol:
                return json.dumps({"error": "symbol is required for action 'signals'"})
            candle_limit = limit if (limit and limit > 50) else 200
            data = await get_price_signals(symbol, interval=interval or "1d", limit=candle_limit)
            return json.dumps({"action": action, "source": f"binance:/api/v3/klines?symbol={symbol.upper()}&interval={interval or '1d'}", "data": data})
        return json.dumps({"error": f"Unknown action '{action}'. Use top_coins, ticker, or signals."})
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": f"Binance market data error: {str(e)}"})


INSTRUCTIONS = f"""
You are a crypto market-data analyst with direct access to live Binance Spot data via the `binance_market_data` tool.

Given an AgentTask (with a 'query' and optional 'gap'), decide which tool calls retrieve the needed numbers:
- To discover or rank the day's liquid coins: call with action="top_coins" (optionally set `limit`).
- For a specific coin's current price/volume: action="ticker", symbol like "BTCUSDT".
- For technical signals (trend, RSI, MACD, moving averages, support/resistance, volume): action="signals", symbol like "BTCUSDT", and a sensible `interval` ("1d" for swing, "4h"/"1h" for intraday).

RULES:
- Always convert a coin name/symbol to a Binance pair by appending "USDT" (e.g. BTC -> BTCUSDT) unless the task specifies another quote.
- You may call the tool multiple times (e.g. top_coins, then signals for the top names relevant to the gap).
- Ground your summary in the actual returned numbers — quote exact prices, % changes, RSI, MACD histogram, SMA values, support/resistance, and volume ratios.
- If the tool returns an error for a symbol, say so and move on; do not invent data.
- Cite the source endpoint string returned by the tool in brackets, e.g. [binance:/api/v3/klines?symbol=BTCUSDT&interval=1d].
- Write a concise, data-dense summary (bullets are fine) addressing the 'gap'/'query'.

Only output JSON. Follow the JSON schema below. Do not output anything else. I will be parsing this with Pydantic so output valid JSON only:
{ToolAgentOutput.model_json_schema()}
"""


def init_binance_agent(config: LLMConfig) -> ResearchAgent:
    selected_model = config.fast_model
    return ResearchAgent(
        name="MarketDataAgent",
        instructions=INSTRUCTIONS,
        tools=[binance_market_data],
        model=selected_model,
        output_type=ToolAgentOutput if model_supports_structured_output(selected_model) else None,
        output_parser=create_type_parser(ToolAgentOutput) if not model_supports_structured_output(selected_model) else None,
    )
