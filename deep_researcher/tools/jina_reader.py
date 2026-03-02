"""
Jina Reader & Search tools providing full access to the Jina AI Reader API.

Two tools exposed as @function_tool for the agents:

1. fetch_page_content(url, ...)
   - Uses r.jina.ai to fetch a single URL with full JavaScript rendering via headless Chrome.
   - Supports all Jina headers: target_selector, wait_for_selector, timeout, cookies,
     respond_with format, proxy_url, image captions, links summary.
   - Ideal for ecommerce product pages where price is JS-rendered.

2. jina_search(query, ...)
   - Uses s.jina.ai to search the web AND fetch+render top 5 result pages.
   - Unlike a normal search API, it returns actual full page content of top results,
     not just snippets. Ideal for finding product listings with confirmed prices.
   - Supports in-site search via site parameter.

No API key required for basic usage (rate-limited to ~20 RPM unauthenticated).
Set JINA_API_KEY in .env for higher limits (high RPM on paid plan).

Jina API docs: https://github.com/jina-ai/reader
"""

import os
import ssl
from typing import Optional
from urllib.parse import quote
import aiohttp
from agents import function_tool

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JINA_READER_BASE = "https://r.jina.ai/"
JINA_SEARCH_BASE = "https://s.jina.ai/"
CONTENT_LENGTH_LIMIT = 15_000   # chars — Jina content is already clean markdown

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Ecommerce-specific price CSS selectors — used as defaults for x-wait-for-selector
# to ensure JS has rendered the price before Jina returns the page
ECOMMERCE_PRICE_SELECTORS = {
    "amazon":   ".a-price, #priceblock_ourprice, #tp_price_block_total_price_ww",
    "flipkart": "._30jeq3, ._25b18c",
    "walmart":  "[itemprop='price'], .price-characteristic",
    "bestbuy":  ".priceView-customer-price span",
    "target":   "[data-test='product-price']",
    "croma":    ".pdp-price, .crm-product-price",
    "noon":     ".price",
    "sharaf":   ".product-price",
}


def _get_api_key() -> Optional[str]:
    return os.getenv("JINA_API_KEY")


def _detect_ecommerce_selector(url: str) -> Optional[str]:
    """Auto-detect the best wait-for-selector for known ecommerce sites."""
    url_lower = url.lower()
    for site, selector in ECOMMERCE_PRICE_SELECTORS.items():
        if site in url_lower:
            return selector
    return None


def _build_reader_headers(
    respond_with: str = "markdown",
    target_selector: Optional[str] = None,
    wait_for_selector: Optional[str] = None,
    timeout: Optional[int] = None,
    with_links_summary: bool = False,
    with_image_captions: bool = False,
    no_cache: bool = True,
    cookie: Optional[str] = None,
    proxy_url: Optional[str] = None,
) -> dict:
    """Build the full set of Jina Reader request headers."""
    headers = {}

    # Auth
    api_key = _get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Output format
    format_map = {
        "markdown": "text/markdown",
        "html":     "text/html",
        "text":     "text/plain",
        "json":     "application/json",
    }
    headers["Accept"] = format_map.get(respond_with, "text/markdown")
    # Also set x-respond-with for non-markdown modes to bypass readability
    if respond_with in ("html", "text"):
        headers["X-Respond-With"] = respond_with

    # Targeting & waiting
    if target_selector:
        headers["X-Target-Selector"] = target_selector
    if wait_for_selector:
        headers["X-Wait-For-Selector"] = wait_for_selector

    # Performance & freshness
    if timeout:
        headers["X-Timeout"] = str(timeout)
    if no_cache:
        headers["X-No-Cache"] = "true"

    # Enrichment
    if with_links_summary:
        headers["X-With-Links-Summary"] = "true"
    if with_image_captions:
        headers["X-With-Generated-Alt"] = "true"

    # Optional cookie forwarding (for sites that require login/session)
    if cookie:
        headers["X-Set-Cookie"] = cookie

    # Optional proxy
    if proxy_url:
        headers["X-Proxy-Url"] = proxy_url

    return headers


# ---------------------------------------------------------------------------
# Tool 1: fetch_page_content — r.jina.ai
# ---------------------------------------------------------------------------

@function_tool
async def fetch_page_content(
    url: str,
    target_selector: Optional[str] = None,
    wait_for_selector: Optional[str] = None,
    timeout: Optional[int] = 30,
    with_links_summary: bool = False,
    respond_with: str = "markdown",
) -> str:
    """Fetch the fully JavaScript-rendered content of a specific web page URL using
    the Jina Reader API (r.jina.ai). Uses headless Chrome, so it works on JS-heavy
    ecommerce pages like Amazon, Flipkart, BestBuy, Walmart, etc.

    Use this tool when you have a DIRECT PRODUCT URL and need to:
    - Extract the exact current price shown on the page
    - Read product title, specs, availability/stock status
    - Read any content that a normal HTTP request would miss due to JavaScript rendering

    IMPORTANT: Always prefer this tool over WebSearchAgent when you already have a URL
    and need its price or page content.

    Args:
        url: Full product URL (e.g. https://www.amazon.in/dp/B0C8S6GR8Y)
        target_selector: Optional CSS selector to extract only a specific part of the
                         page (e.g. ".a-price" for Amazon price box). Leave None to
                         get the full page content.
        wait_for_selector: Optional CSS selector to wait for before returning content.
                           If None, auto-detected for known ecommerce sites.
        timeout: Max seconds to wait for page rendering (default 20). Increase to 30+
                 for slow sites or SPAs that load content late.
        with_links_summary: If True, appends a summary of all links found on the page.
                            Useful for finding related product URLs.
        respond_with: Output format — "markdown" (default, best for LLMs), "text"
                      (plain text, no formatting), or "html" (raw HTML).

    Returns:
        Clean Markdown (or text/html) of the page content, trimmed to 15,000 chars.
        Returns an error string if the fetch fails.
    """
    if not url:
        return "Error: empty URL provided."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Only apply auto ecommerce selector if caller didn't provide one AND didn't explicitly
    # pass wait_for_selector=None to opt out. We do NOT default it to avoid hanging on
    # bot-protected sites (Flipkart, Amazon) that block headless browsers.
    effective_wait = wait_for_selector  # Caller controls this explicitly

    headers = _build_reader_headers(
        respond_with=respond_with,
        target_selector=target_selector,
        wait_for_selector=effective_wait,
        timeout=timeout,
        with_links_summary=with_links_summary,
        no_cache=True,
    )

    jina_url = f"{JINA_READER_BASE}{url}"
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                jina_url,
                headers=headers,
                # Client timeout is generous — Jina's server handles rendering timeout
                # The X-Timeout header controls rendering; this just waits for the HTTP response
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    if len(content) > CONTENT_LENGTH_LIMIT:
                        content = content[:CONTENT_LENGTH_LIMIT] + (
                            "\n\n[Content trimmed — page continues beyond this point]"
                        )
                    return content
                else:
                    return (
                        f"Jina Reader error: HTTP {response.status} for URL: {url}. "
                        f"Jina URL used: {jina_url}"
                    )
    except Exception as e:
        return f"Jina Reader exception: {type(e).__name__}: {e}. URL: {url}"


# ---------------------------------------------------------------------------
# Tool 2: jina_search — s.jina.ai
# ---------------------------------------------------------------------------

@function_tool
async def jina_search(
    query: str,
    site: Optional[str] = None,
    respond_with: str = "markdown",
) -> str:
    """Search the web using Jina Search (s.jina.ai) and get the FULL RENDERED CONTENT
    of the top 5 search results — not just snippets.

    Unlike WebSearchAgent which returns brief search snippets, Jina Search fetches and
    renders each result page fully (including JavaScript), returning actual page content.
    This is ideal for finding product listings with confirmed prices when you don't yet
    have a direct URL.

    Use this tool when:
    - You need to find a product on a specific competitor site and want prices in one step
    - WebSearchAgent returned only snippets without price data
    - You want to search within a specific site (set the 'site' parameter)

    Args:
        query: Search query (e.g. "OnePlus Nord Buds 3 Pro site:flipkart.com")
        site: Optional domain to restrict search to (e.g. "flipkart.com"). When set,
              performs an in-site search on that domain.
        respond_with: Output format — "markdown" (default) or "text".

    Returns:
        Full rendered content of top 5 search results as Markdown, trimmed to 15,000 chars.
    """
    if not query:
        return "Error: empty query provided."

    # Build URL: encode query and optionally append site parameter
    encoded_query = quote(query)
    search_url = f"{JINA_SEARCH_BASE}{encoded_query}"
    if site:
        search_url += f"?site={quote(site)}"

    headers = _build_reader_headers(
        respond_with=respond_with,
        no_cache=True,
    )

    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                search_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    if len(content) > CONTENT_LENGTH_LIMIT:
                        content = content[:CONTENT_LENGTH_LIMIT] + (
                            "\n\n[Content trimmed — search results continue beyond this point]"
                        )
                    return content
                else:
                    return (
                        f"Jina Search error: HTTP {response.status} for query: '{query}'."
                    )
    except Exception as e:
        return f"Jina Search exception: {type(e).__name__}: {e}. Query: '{query}'"
