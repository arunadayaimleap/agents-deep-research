#!/usr/bin/env python3
"""Minimal test for Jina fetch_page_content tool, bypassing the full agent stack."""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import ssl
import aiohttp

JINA_READER_BASE = "https://r.jina.ai/"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

async def fetch(url: str, wait_selector: str = None, jina_timeout: int = 30):
    headers = {
        "Accept": "text/markdown",
        "X-No-Cache": "true",
        "X-Timeout": str(jina_timeout),  # Jina server-side rendering timeout
    }
    api_key = os.getenv("JINA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        print(f"Using JINA_API_KEY: {api_key[:8]}...")
    else:
        print("No JINA_API_KEY found — using unauthenticated (rate-limited)")

    if wait_selector:
        headers["X-Wait-For-Selector"] = wait_selector
        print(f"Wait-for-selector: {wait_selector}")

    jina_url = f"{JINA_READER_BASE}{url}"
    print(f"Fetching: {jina_url}")
    print(f"Jina timeout: {jina_timeout}s | aiohttp timeout: 120s\n")

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(
            jina_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),  # wait up to 120s for Jina response
        ) as resp:
            print(f"HTTP Status: {resp.status}")
            content = await resp.text()
            print(content[:3000])
            print(f"\n[Total length: {len(content)} chars]")

async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.amazon.in/dp/B0FMDL81GS"
    selector = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    await fetch(url, wait_selector=selector)

asyncio.run(main())
