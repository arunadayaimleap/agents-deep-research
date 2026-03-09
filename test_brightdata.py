#!/usr/bin/env python3
import asyncio

from dotenv import load_dotenv

load_dotenv()

from deep_researcher.tools.brightdata_tools import brightdata_search
from deep_researcher.tools.web_search import create_web_search_tool
from deep_researcher.llm_config import create_default_config


async def main():
    queries = [
        "Who is the CEO of Enel Colombia?",
        "What is the official website of Drummond Colombia?",
    ]

    for query in queries:
        results = await brightdata_search(query, max_results=3, include_ai_overview=True)
        if not results or "error" in results[0]:
            raise RuntimeError(results[0]["error"] if results else "No Bright Data results")
        print(f"\nQUERY: {query}")
        print(f"RESULT COUNT: {len(results)}")
        print(f"TOP TITLE: {results[0].get('title', '')[:120]}")
        print(f"TOP URL: {results[0].get('url', '')[:120]}")

    config = create_default_config()
    tool = create_web_search_tool(config)
    print(f"\nWEB SEARCH TOOL INITIALIZED: {tool.name}")


if __name__ == "__main__":
    asyncio.run(main())
