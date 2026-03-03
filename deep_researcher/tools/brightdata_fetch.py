"""
BrightData Web Unlocker tool — fetches any URL via BrightData's residential proxy
network with automatic CAPTCHA solving and bot-detection bypass.

Use this as a fallback when Jina Reader (fetch_page_content) fails on heavily
anti-bot protected sites (e.g. Amazon.com, Amazon.in, Walmart, etc.).

Key features:
- Auto-detects country code from the URL domain (.in→in, .co.uk→gb, .com→us etc.)
- Returns clean Markdown via data_format="markdown"
- Uses the 'data_unblocker' zone (BrightData's Web Unlocker product)
- Configurable: set BRIGHTDATA_ZONE in .env to override zone name

Requires: BRIGHTDATA_API_KEY in .env
"""

import os
import ssl
import json
from typing import Optional
from urllib.parse import urlparse
import aiohttp
from agents import function_tool

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# Domain → ISO 3166-1 alpha-2 country code map
# Sorted longest-suffix first so .com.au matches before .com
# ---------------------------------------------------------------------------
_DOMAIN_COUNTRY: list[tuple[str, str]] = sorted([
    (".com.au", "au"),
    (".com.br", "br"),
    (".com.mx", "mx"),
    (".co.uk",  "gb"),
    (".co.in",  "in"),
    (".co.jp",  "jp"),
    (".co.nz",  "nz"),
    (".co.za",  "za"),
    (".com",    "us"),   # default — must come AFTER all .com.XX
    (".in",     "in"),
    (".ca",     "ca"),
    (".de",     "de"),
    (".fr",     "fr"),
    (".ae",     "ae"),
    (".sa",     "sa"),
    (".jp",     "jp"),
    (".it",     "it"),
    (".es",     "es"),
    (".nl",     "nl"),
    (".sg",     "sg"),
    (".gb",     "gb"),
    (".uk",     "gb"),
], key=lambda x: -len(x[0]))   # longest suffix first


def _country_from_url(url: str) -> str:
    """Extract ISO country code from URL domain. Falls back to 'us'."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lstrip("www.")
    except Exception:
        return "us"
    for suffix, code in _DOMAIN_COUNTRY:
        if hostname.endswith(suffix):
            return code
    return "us"


def _get_config() -> tuple[str, str]:
    """Return (api_key, zone_name). Raises if key missing."""
    api_key = os.getenv("BRIGHTDATA_API_KEY", "")
    zone = os.getenv("BRIGHTDATA_ZONE", "data_unblocker")
    return api_key, zone


# ---------------------------------------------------------------------------
# @function_tool
# ---------------------------------------------------------------------------

@function_tool
async def brightdata_fetch(
    url: str,
    country: Optional[str] = None,
) -> str:
    """Fetch a fully rendered web page via BrightData Web Unlocker, bypassing
    anti-bot protections, CAPTCHAs, and IP blocks on ecommerce sites.

    Use this tool when fetch_page_content (Jina Reader) fails or returns
    insufficient/blocked content on a specific product URL. BrightData routes
    through residential proxies and handles bot challenges automatically.

    Best for: Amazon (.com, .in, .co.uk), Walmart, Target, BestBuy, Flipkart,
    and any other site that blocks standard scrapers.

    Returns clean Markdown of the page — including JS-rendered price, stock
    status, product title, and specs.

    Args:
        url: Full product URL (e.g. https://www.amazon.com/dp/B07BB4D2RP)
        country: Optional ISO country code override (e.g. "us", "in", "gb").
                 Auto-detected from URL domain if not provided.
                 (.com → us, .in → in, .co.uk → gb, .com.au → au, etc.)

    Returns:
        Clean Markdown content of the page, trimmed to 15,000 chars.
        Returns an error string if the fetch fails.
    """
    if not url:
        return "Error: empty URL provided."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    api_key, zone = _get_config()
    if not api_key:
        return "Error: BRIGHTDATA_API_KEY not set in environment."

    # Auto-detect country from domain if not specified
    effective_country = (country or "").strip().lower() or _country_from_url(url)

    payload = {
        "zone": zone,
        "url": url,
        "format": "json",
        "method": "GET",
        "data_format": "markdown",
        "country": effective_country,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                BRIGHTDATA_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                raw = await response.text()

                if response.status != 200:
                    return (
                        f"BrightData error: HTTP {response.status}. "
                        f"Response: {raw[:500]}"
                    )

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return f"BrightData returned non-JSON response: {raw[:500]}"

                inner_status = data.get("status_code", 0)
                body = data.get("body", "")

                if inner_status != 200:
                    return (
                        f"BrightData fetched URL but page returned status {inner_status}. "
                        f"Content: {body[:300]}"
                    )

                if not body:
                    return f"BrightData returned empty body for URL: {url}"

                return body

    except Exception as e:
        return f"BrightData exception: {type(e).__name__}: {e}. URL: {url}"
