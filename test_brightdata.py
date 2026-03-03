#!/usr/bin/env python3
"""
Test for BrightData Web Unlocker API with auto domain→country detection.

Usage:
  python test_brightdata.py
  python test_brightdata.py "https://www.amazon.com/dp/B07BB4D2RP"
  python test_brightdata.py "https://www.amazon.in/dp/B0FMDL81GS"
  python test_brightdata.py "https://www.flipkart.com/some-product" in

Set BRIGHTDATA_ZONE in .env if your zone name differs from web_unlocker1.
"""
import asyncio
import json
import os
import sys
import ssl
import aiohttp
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")
# Zone name from your BrightData dashboard — override via BRIGHTDATA_ZONE env var
BRIGHTDATA_ZONE = os.getenv("BRIGHTDATA_ZONE", "web_unlocker1")
BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# Domain → Country code mapping (ISO 3166-1 alpha-2)
# .com is treated as US by default
# ---------------------------------------------------------------------------
DOMAIN_COUNTRY_MAP = {
    ".in":      "in",   # India
    ".co.uk":   "gb",   # United Kingdom
    ".co.in":   "in",   # India
    ".com.au":  "au",   # Australia
    ".ca":      "ca",   # Canada
    ".de":      "de",   # Germany
    ".fr":      "fr",   # France
    ".ae":      "ae",   # UAE
    ".sa":      "sa",   # Saudi Arabia
    ".jp":      "jp",   # Japan
    ".com.br":  "br",   # Brazil
    ".com.mx":  "mx",   # Mexico
    ".it":      "it",   # Italy
    ".es":      "es",   # Spain
    ".nl":      "nl",   # Netherlands
    ".com":     "us",   # Default → USA
}

def detect_country_from_url(url: str) -> str:
    """Extract country code from URL domain. Defaults to 'us' for .com and unknown domains."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lstrip("www.")
    except Exception:
        return "us"

    # Check longest suffix first to avoid .com matching before .com.au
    for suffix, country in sorted(DOMAIN_COUNTRY_MAP.items(), key=lambda x: -len(x[0])):
        if hostname.endswith(suffix):
            return country

    return "us"  # fallback


async def brightdata_fetch(url: str, country: str = None) -> dict:
    if not BRIGHTDATA_API_KEY:
        print("ERROR: BRIGHTDATA_API_KEY not set in .env")
        sys.exit(1)

    # Auto-detect country from domain if not explicitly provided
    effective_country = country or detect_country_from_url(url)

    payload = {
        "zone": BRIGHTDATA_ZONE,
        "url": url,
        "format": "json",
        "method": "GET",
        "data_format": "markdown",
        "country": effective_country,
    }

    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"BrightData API Key : {BRIGHTDATA_API_KEY[:8]}...")
    print(f"Zone               : {BRIGHTDATA_ZONE}")
    print(f"Target URL         : {url}")
    print(f"Country (detected) : {effective_country}")
    print("-" * 60)

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(
            BRIGHTDATA_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            print(f"HTTP Status: {resp.status}")
            raw = await resp.text()

            if resp.status != 200:
                print(f"Error:\n{raw[:2000]}")
                return {}

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                print(f"Non-JSON response:\n{raw[:3000]}")
                return {}


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.amazon.com/Whirlpool-Microwave-Fingerprint-Resistant-Electronic/dp/B07BB4D2RP"
    country = sys.argv[2] if len(sys.argv) > 2 else None  # None = auto-detect

    data = await brightdata_fetch(url, country)
    if not data:
        print("No data returned.")
        return

    status = data.get("status_code")
    body = data.get("body", "")

    print(f"\nInner status_code  : {status}")
    print(f"Body length        : {len(body)} chars")
    print("\n--- First 3000 chars of body ---\n")
    print(body[:3000])

    # Check price signals
    for term in ["price", "$", "₹", "£", "€", "buy", "add to cart"]:
        idx = body.lower().find(term.lower())
        if idx >= 0:
            print(f"\n✅ '{term}' found at pos {idx}: ...{body[max(0,idx-80):idx+150]}...")
            break
    else:
        print("\n⚠️  No price signals found in response body")

if __name__ == "__main__":
    asyncio.run(main())
