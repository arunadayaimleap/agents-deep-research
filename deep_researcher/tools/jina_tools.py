"""
Jina AI Reader and Search integration.

- Reader API (r.jina.ai): Convert URL to LLM-friendly markdown
- Search API (s.jina.ai): Web search with content returned

Requires JINA_API_KEY in .env for full functionality.
Reader works without key (20 RPM); Search requires key.
"""

from typing import List, Optional
from urllib.parse import quote

import aiohttp
from agents import function_tool
from dotenv import load_dotenv

from ..utils.os import get_env_with_prefix

load_dotenv()

JINA_API_KEY = get_env_with_prefix("JINA_API_KEY")
READER_BASE = "https://r.jina.ai"
SEARCH_BASE = "https://s.jina.ai"
CONTENT_LENGTH_LIMIT = 12000


def _jina_headers() -> dict:
    """Headers for Jina API requests. API key enables higher rate limits."""
    headers = {"Accept": "application/json"}
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"
    return headers


async def read_url(url: str, max_length: int = CONTENT_LENGTH_LIMIT) -> str:
    """
    Fetch URL content via Jina Reader. Returns LLM-friendly markdown.
    Handles PDFs, dynamic pages, and complex layouts.

    Args:
        url: Full URL to fetch (e.g. https://example.com/page)
        max_length: Max chars to return (default 12000)

    Returns:
        Markdown text or error message.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    reader_url = f"{READER_BASE}/{url}"
    headers = _jina_headers()
    headers["Accept"] = "application/json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                reader_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    return f"Error fetching {url}: HTTP {response.status}"

                ct = response.content_type or ""
                if "json" in ct:
                    data = await response.json()
                    # Handle nested structures: data.content, data.data, or flat content/title
                    content = data.get("content") or data.get("data")
                    if content is None:
                        content = data
                    if isinstance(content, dict):
                        text = content.get("content", content.get("markdown", content.get("text", str(content))))
                    elif isinstance(content, str):
                        text = content
                    else:
                        text = str(data)
                    title = data.get("title") or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("title", "")
                    if isinstance(title, dict):
                        title = title.get("title", "")
                else:
                    raw = await response.text()
                    if "Markdown Content:" in raw:
                        text = raw.split("Markdown Content:", 1)[1].strip()
                        title = ""
                        if raw.startswith("Title:"):
                            title = raw.split("\n")[0].replace("Title:", "").strip()
                    else:
                        text = raw

                if title and not text.startswith("#"):
                    text = f"# {title}\n\n{text}"

                if len(text) > max_length:
                    text = text[:max_length] + "\n...[Content Truncated]..."

                return text
    except aiohttp.ClientError as e:
        return f"Error fetching {url}: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


async def jina_search(
    query: str, max_results: int = 5, max_content_length: int = CONTENT_LENGTH_LIMIT
) -> List[dict]:
    """
    Web search via Jina Search. Returns top results with full content.
    Requires JINA_API_KEY.

    Args:
        query: Search query
        max_results: Max results to return (1-5)
        max_content_length: Max chars per result content

    Returns:
        List of dicts with url, title, description, text
    """
    if not JINA_API_KEY:
        return [{"error": "JINA_API_KEY required for Jina Search. Set it in .env"}]

    search_url = f"{SEARCH_BASE}/?q={quote(query)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                search_url,
                headers=_jina_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    return [{"error": f"Jina Search HTTP {response.status}"}]

                data = await response.json()
                entries = data.get("data", data.get("results", []))
                if not isinstance(entries, list):
                    entries = [data]

                results = []
                for i, entry in enumerate(entries[:max_results]):
                    if isinstance(entry, dict):
                        url = entry.get("url", entry.get("link", ""))
                        title = entry.get("title", "")
                        content = entry.get("content", entry.get("body", entry.get("snippet", "")))
                        if isinstance(content, str) and len(content) > max_content_length:
                            content = content[:max_content_length] + "..."
                        results.append({
                            "url": url,
                            "title": title,
                            "description": entry.get("description", content[:300] if content else ""),
                            "text": content or "",
                        })
                    else:
                        results.append({"url": "", "title": "", "description": "", "text": str(entry)})

                return results
    except Exception as e:
        return [{"error": f"Jina Search error: {str(e)}"}]


# --- Function tools for agents ---

@function_tool
async def read_url_with_jina(url: str) -> str:
    """Fetch a URL and return its content as clean markdown. Use for specific pages (Contact, About, etc.).
    Handles PDFs and complex pages. Prefer this over open_page when you have a direct URL.

    Args:
        url: Full URL to read (e.g. https://terpel.com/contacto)

    Returns:
        Markdown content or error message.
    """
    return await read_url(url)


@function_tool
async def search_with_jina(query: str) -> str:
    """Search the web and return results with full content. Use when you need up-to-date info.
    Requires JINA_API_KEY.

    Args:
        query: Search query (3-6 words recommended)

    Returns:
        Formatted string of search results with titles, URLs, and content.
    """
    results = await jina_search(query, max_results=5)
    if not results:
        return "No search results found."
    if "error" in results[0]:
        return results[0]["error"]

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"--- Result {i}: {r.get('title', 'Untitled')} ---")
        lines.append(f"URL: {r.get('url', '')}")
        lines.append(f"Content:\n{r.get('text', r.get('description', ''))}")
        lines.append("")
    return "\n".join(lines)
