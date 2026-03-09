#!/usr/bin/env python3
"""Test to show verbose tool logging."""
import asyncio
from dotenv import load_dotenv

load_dotenv()

from deep_researcher.tools.web_search import create_web_search_tool
from deep_researcher.llm_config import create_default_config
from deep_researcher.tools.sendgrid_tools import send_test_email


async def main():
    print("=" * 70)
    print("VERBOSE TOOL LOGGING TEST")
    print("=" * 70)
    print()
    
    config = create_default_config()
    web_search_tool = create_web_search_tool(config)
    
    # Test 1: Web Search
    print("[TEST 1] Web Search Tool")
    print("-" * 70)
    results = await web_search_tool.func("Python programming language")
    print(f"Results type: {type(results)}")
    if isinstance(results, list):
        print(f"Got {len(results)} results")
        for i, result in enumerate(results[:2], 1):
            print(f"\nResult {i}:")
            print(f"  URL: {result.url}")
            print(f"  Title: {result.title}")
            print(f"  Text length: {len(result.text)} chars")
    print()
    
    # Test 2: SendGrid (if configured)
    print("[TEST 2] SendGrid Email Sending")
    print("-" * 70)
    result = await send_test_email("test@example.com")
    print(f"SendGrid result: {result}")
    print()
    
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
