#!/usr/bin/env python3
"""
Test script for Bright Data Unlocker API integration.
Tests markdown extraction from various websites.
"""
import asyncio
from dotenv import load_dotenv

load_dotenv()

from deep_researcher.tools.brightdata_tools import brightdata_unlock_url


async def main():
    test_urls = [
        "https://example.com",
        "https://www.python.org",
        "https://drummondltd.com/en/",
    ]

    print("Testing Bright Data Unlocker API with markdown conversion...\n")

    for url in test_urls:
        print(f"Fetching: {url}")
        content = await brightdata_unlock_url(url, max_length=500, data_format="markdown")

        if content.startswith("Error"):
            print(f"  ❌ {content}\n")
        else:
            print(f"  ✓ Success, content length: {len(content)} chars")
            print(f"  Preview: {content[:200]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
