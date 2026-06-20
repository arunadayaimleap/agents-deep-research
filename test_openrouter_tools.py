#!/usr/bin/env python3
"""Smoke test OpenRouter web_search and web_fetch server tools."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from deep_researcher.tools.openrouter_server_tools import (
    openrouter_datetime,
    openrouter_web_fetch,
    openrouter_web_search,
)


async def main() -> int:
    print("=== OpenRouter datetime ===")
    dt = await openrouter_datetime("UTC")
    if not dt.get("datetime"):
        print("FAIL: no datetime")
        return 1
    print(f"  {dt.get('datetime')} ({dt.get('timezone')})")

    print("\n=== OpenRouter web_search ===")
    hits = await openrouter_web_search("Boeing 737-800 CFM56 MRO market size", max_results=3)
    if not hits:
        print("FAIL: no search results")
        return 1
    for i, h in enumerate(hits, 1):
        print(f"  {i}. {h.get('title') or '(no title)'}")
        print(f"     {h.get('url')}")

    url = hits[0].get("url") or ""
    if not url.startswith("http"):
        print("SKIP web_fetch: no http URL in first hit")
        return 0

    print("\n=== OpenRouter web_fetch ===")
    page = await openrouter_web_fetch(url, max_content_chars=3000)
    content = page.get("content") or ""
    print(f"  URL: {url}")
    print(f"  Chars: {len(content)}")
    print(f"  Preview: {content[:400].replace(chr(10), ' ')}...")
    if len(content) < 50:
        print("WARN: very short fetch content")
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
