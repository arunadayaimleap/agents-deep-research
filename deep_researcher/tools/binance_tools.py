"""
Binance Spot market-data tools for crypto trade-signal research.

Public market-data endpoints do not require authentication, but the API key
(``BINANCE_API_KEY``) is attached as the ``X-MBX-APIKEY`` header when present,
and signed requests are supported via ``BINANCE_SECRET_KEY`` for account endpoints.

Docs:
- https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- Public market-data base URL: https://data-api.binance.vision (no auth, geo-friendly)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

# Primary first, then public market-data mirror as fallback (no auth, fewer geo blocks).
_BASE_URLS = [
    os.getenv("BINANCE_BASE_URL", "https://api.binance.com"),
    "https://data-api.binance.vision",
]

# Exclude leveraged tokens and stable/wrapped quote-side noise from "top coins".
_LEVERAGED_SUFFIXES = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
_STABLE_BASES = {
    "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDT", "EUR", "EURI",
    "USD1", "USDE", "PYUSD", "GUSD", "USDD", "USTC", "AEUR", "XUSD", "USDS",
}


def _api_key() -> str:
    return os.getenv("BINANCE_API_KEY", "")


def _secret_key() -> str:
    return os.getenv("BINANCE_SECRET_KEY", "")


def _headers() -> dict[str, str]:
    key = _api_key()
    return {"X-MBX-APIKEY": key} if key else {}


async def _request(path: str, params: dict[str, Any] | None = None, *, signed: bool = False) -> Any:
    """GET a Binance endpoint, trying each base URL until one succeeds."""
    params = dict(params or {})
    if signed:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        signature = hmac.new(
            _secret_key().encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature

    last_err: Exception | None = None
    for base in _BASE_URLS:
        # Signed/account endpoints only exist on the main API host.
        if signed and "data-api" in base:
            continue
        url = f"{base}{path}"
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=_headers()) as resp:
                    body = await resp.text()
                    if resp.status >= 400:
                        last_err = RuntimeError(f"Binance HTTP {resp.status} at {url}: {body[:200]}")
                        continue
                    return json.loads(body)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"Binance request failed for {path}: {last_err}")


# ------- INDICATOR HELPERS (pure Python) -------


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    out = [ema]
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
        out.append(ema)
    return out


def _ema(values: list[float], period: int) -> float | None:
    series = _ema_series(values, period)
    return series[-1] if series else None


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float | None]:
    if len(closes) < slow + signal:
        return {"macd": None, "signal": None, "histogram": None}
    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)
    # Align series lengths (slow EMA starts later).
    offset = len(ema_fast) - len(ema_slow)
    ema_fast = ema_fast[offset:]
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_series = _ema_series(macd_line, signal)
    if not signal_series:
        return {"macd": round(macd_line[-1], 4), "signal": None, "histogram": None}
    macd_val = macd_line[-1]
    signal_val = signal_series[-1]
    return {
        "macd": round(macd_val, 4),
        "signal": round(signal_val, 4),
        "histogram": round(macd_val - signal_val, 4),
    }


# ------- PUBLIC MARKET-DATA FUNCTIONS -------


async def get_top_symbols(quote: str = "USDT", limit: int = 15) -> list[dict[str, Any]]:
    """Top tradable coins by 24h quote volume (a liquidity proxy)."""
    data = await _request("/api/v3/ticker/24hr")
    rows: list[dict[str, Any]] = []
    for t in data:
        sym = t.get("symbol", "")
        if not sym.endswith(quote):
            continue
        if sym.endswith(_LEVERAGED_SUFFIXES):
            continue
        base = sym[: -len(quote)]
        if base in _STABLE_BASES:
            continue
        try:
            quote_vol = float(t.get("quoteVolume", 0) or 0)
            rows.append(
                {
                    "symbol": sym,
                    "base": base,
                    "last_price": float(t.get("lastPrice", 0) or 0),
                    "price_change_pct_24h": round(float(t.get("priceChangePercent", 0) or 0), 2),
                    "quote_volume_24h": quote_vol,
                    "high_24h": float(t.get("highPrice", 0) or 0),
                    "low_24h": float(t.get("lowPrice", 0) or 0),
                    "trade_count_24h": int(t.get("count", 0) or 0),
                }
            )
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda r: r["quote_volume_24h"], reverse=True)
    return rows[:limit]


async def get_24hr(symbol: str) -> dict[str, Any]:
    """24h rolling stats for a single symbol."""
    t = await _request("/api/v3/ticker/24hr", {"symbol": symbol.upper()})
    return {
        "symbol": t.get("symbol"),
        "last_price": float(t.get("lastPrice", 0) or 0),
        "price_change_pct_24h": round(float(t.get("priceChangePercent", 0) or 0), 2),
        "quote_volume_24h": float(t.get("quoteVolume", 0) or 0),
        "high_24h": float(t.get("highPrice", 0) or 0),
        "low_24h": float(t.get("lowPrice", 0) or 0),
        "weighted_avg_price": float(t.get("weightedAvgPrice", 0) or 0),
        "trade_count_24h": int(t.get("count", 0) or 0),
    }


async def get_klines(symbol: str, interval: str = "1d", limit: int = 200) -> list[dict[str, float]]:
    """Parsed OHLCV candles for a symbol."""
    raw = await _request(
        "/api/v3/klines",
        {"symbol": symbol.upper(), "interval": interval, "limit": min(limit, 1000)},
    )
    out: list[dict[str, float]] = []
    for k in raw:
        out.append(
            {
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
                "quote_volume": float(k[7]),
            }
        )
    return out


async def get_price_signals(
    symbol: str, interval: str = "1d", limit: int = 200
) -> dict[str, Any]:
    """Compute trend, RSI, MACD, moving averages, support/resistance, and volume context."""
    symbol = symbol.upper()
    candles = await get_klines(symbol, interval=interval, limit=limit)
    if len(candles) < 30:
        return {"symbol": symbol, "interval": interval, "error": "insufficient kline history"}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["volume"] for c in candles]
    last_close = closes[-1]

    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    rsi14 = _rsi(closes, 14)
    macd = _macd(closes)

    lookback = min(30, len(candles))
    recent_low = min(lows[-lookback:])
    recent_high = max(highs[-lookback:])

    avg_vol_20 = _sma(volumes, 20)
    last_vol = volumes[-1]
    vol_ratio = round(last_vol / avg_vol_20, 2) if avg_vol_20 else None

    # Trend classification from price vs moving averages and MACD.
    trend = "neutral"
    if sma50 and sma20:
        if last_close > sma50 and sma20 >= sma50:
            trend = "bullish"
        elif last_close < sma50 and sma20 <= sma50:
            trend = "bearish"
    if macd.get("histogram") is not None:
        if trend == "neutral" and macd["histogram"] > 0:
            trend = "bullish-leaning"
        elif trend == "neutral" and macd["histogram"] < 0:
            trend = "bearish-leaning"

    rsi_state = None
    if rsi14 is not None:
        if rsi14 >= 70:
            rsi_state = "overbought"
        elif rsi14 <= 30:
            rsi_state = "oversold"
        else:
            rsi_state = "neutral"

    return {
        "symbol": symbol,
        "interval": interval,
        "candles_analyzed": len(candles),
        "last_close": last_close,
        "trend": trend,
        "rsi14": rsi14,
        "rsi_state": rsi_state,
        "macd": macd,
        "sma20": round(sma20, 6) if sma20 else None,
        "sma50": round(sma50, 6) if sma50 else None,
        "sma200": round(sma200, 6) if sma200 else None,
        "support": round(recent_low, 6),
        "resistance": round(recent_high, 6),
        "support_lookback_bars": lookback,
        "last_volume": last_vol,
        "avg_volume_20": round(avg_vol_20, 4) if avg_vol_20 else None,
        "volume_vs_avg_ratio": vol_ratio,
    }


async def get_account_status() -> dict[str, Any]:
    """Signed account snapshot (verifies API key/secret). Best-effort; market data is the primary use."""
    if not _secret_key():
        return {"error": "BINANCE_SECRET_KEY not set; signed endpoints unavailable"}
    try:
        data = await _request("/api/v3/account", signed=True)
        balances = [
            b for b in data.get("balances", []) if float(b.get("free", 0) or 0) > 0
        ]
        return {
            "can_trade": data.get("canTrade"),
            "account_type": data.get("accountType"),
            "nonzero_balances": balances[:25],
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
