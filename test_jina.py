#!/usr/bin/env python3
"""Test Jina Reader and Search integration."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from deep_researcher.tools.jina_tools import read_url, jina_search


async def test_reader():
    print("\n--- Jina Reader (example.com) ---")
    result = await read_url("https://example.com")
    print("Length:", len(result))
    print("Preview:", result[:300] + "..." if len(result) > 300 else result)
    assert "example" in result.lower() or "Example" in result, "Expected example content"


async def test_search():
    if not os.getenv("JINA_API_KEY"):
        print("\n--- Jina Search: SKIPPED (no JINA_API_KEY) ---")
        return
    print("\n--- Jina Search ---")
    results = await jina_search("Terpel Colombia fuel company", max_results=2)
    if results and "error" in results[0]:
        print("Error:", results[0]["error"])
        return
    print("Results:", len(results))
    for i, r in enumerate(results[:2], 1):
        print(f"  {i}. {r.get('title', '')[:50]}... | {r.get('url', '')[:40]}...")
        print(f"     Content len: {len(r.get('text', ''))}")


async def test_tools():
    print("\n--- read_url_with_jina (uses read_url) ---")
    out = await read_url("https://example.com")
    print("OK, length:", len(out))

    if os.getenv("JINA_API_KEY"):
        print("\n--- jina_search (tool backend) ---")
        results = await jina_search("Enel Colombia", max_results=1)
        out = str(results)
        print("OK, results:", len(results))
        if results and "error" not in results[0]:
            print("Preview:", results[0].get("text", "")[:300] + "...")


async def main():
    print("JINA_API_KEY set:", bool(os.getenv("JINA_API_KEY")))
    await test_reader()
    await test_search()
    await test_tools()
    print("\n--- All Jina tests passed ---")


if __name__ == "__main__":
    asyncio.run(main())
