"""
Jina Reader tool — fetches a single URL's fully-rendered content via the Jina AI
Reader API (https://r.jina.ai), which renders JavaScript and returns clean Markdown.

Usage: simply prepend "https://r.jina.ai/" to any URL.
No API key required for basic usage (rate-limited).
Set JINA_API_KEY in .env for higher rate limits / priority access.

Returns a clean Markdown string of the page content — including price data on
ecommerce sites that are JavaScript-rendered (Amazon, Flipkart, etc.)
"""

import os
import ssl
import aiohttp
from agents import function_tool

JINA_BASE_URL = "https://r.jina.ai/"
CONTENT_LENGTH_LIMIT = 15000  # Higher than aiohttp scraper — Jina content is already clean

# Reuse the ssl context pattern from the rest of the codebase
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def _build_headers() -> dict:
    """Build Jina API request headers. Uses API key if available."""
    headers = {
        "Accept": "text/markdown",               # Request Markdown output
        "X-Return-Format": "markdown",           # Explicit format hint
        "X-No-Cache": "true",                    # Always fetch fresh content
        "X-Remove-Selector": "header,footer,nav,script,style",  # Strip noise
    }
    api_key = os.getenv("JINA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


@function_tool
async def fetch_page_content(url: str) -> str:
    """Fetch the fully-rendered content of a web page using the Jina Reader API.

    Use this tool when you have a specific product URL and need to extract its
    price, title, availability, or other details. Unlike a basic web scraper,
    this tool renders JavaScript — making it effective on ecommerce sites like
    Amazon, Flipkart, BestBuy, Walmart, etc.

    Args:
        url: The full URL of the page to fetch (e.g. https://www.amazon.in/dp/B0C8S6GR8Y)

    Returns:
        The page content as clean Markdown text, trimmed to avoid token overuse.
        Returns an error string if the fetch fails.
    """
    if not url:
        return "Error: empty URL provided."

    # Ensure URL has a protocol
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    jina_url = f"{JINA_BASE_URL}{url}"

    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                jina_url,
                headers=_build_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    # Trim to limit context size
                    if len(content) > CONTENT_LENGTH_LIMIT:
                        content = content[:CONTENT_LENGTH_LIMIT] + "\n\n[Content trimmed — page continues beyond this point]"
                    return content
                else:
                    return (
                        f"Error fetching page via Jina Reader: HTTP {response.status}. "
                        f"URL attempted: {jina_url}"
                    )
    except Exception as e:
        return f"Error fetching page via Jina Reader: {str(e)}. URL: {url}"
