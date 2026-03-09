import os
from typing import List
from urllib.parse import quote

import aiohttp
from dotenv import load_dotenv

load_dotenv()

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")
BRIGHTDATA_SERP_ZONE = os.getenv("BRIGHTDATA_SERP_ZONE") or os.getenv("BRIGHTDATA_ZONE")
BRIGHTDATA_UNLOCKER_ZONE = os.getenv("BRIGHTDATA_UNLOCKER_ZONE") or os.getenv("BRIGHTDATA_ZONE")
BRIGHTDATA_REQUEST_URL = "https://api.brightdata.com/request"


async def brightdata_search(
    query: str,
    max_results: int = 5,
    include_ai_overview: bool = True,
) -> List[dict]:
    """
    Search Google via Bright Data SERP API.

    The query can be natural language, including full questions.
    Returns normalized result dictionaries with url, title, description, and optional ai_overview text.
    """
    if not BRIGHTDATA_API_KEY:
        return [{"error": "BRIGHTDATA_API_KEY required for Bright Data search. Set it in .env"}]
    if not BRIGHTDATA_SERP_ZONE:
        return [{"error": "BRIGHTDATA_SERP_ZONE required for Bright Data search. Set it in .env"}]

    google_url = f"https://www.google.com/search?q={quote(query)}&brd_json=1"
    if include_ai_overview:
        google_url += "&brd_ai_overview=2"

    payload = {
        "zone": BRIGHTDATA_SERP_ZONE,
        "url": google_url,
        "format": "raw",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                BRIGHTDATA_REQUEST_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    return [{"error": f"Bright Data search HTTP {response.status}: {text[:300]}"}]
                data = await response.json()

        results: List[dict] = []

        ai_texts = ((data.get("ai_overview") or {}).get("texts") or [])
        ai_references = ((data.get("ai_overview") or {}).get("references") or [])
        ai_snippets = [
            item.get("snippet", "").strip()
            for item in ai_texts
            if isinstance(item, dict) and item.get("snippet")
        ]
        if ai_snippets:
            ai_url = ai_references[0].get("href", "") if ai_references else ""
            results.append(
                {
                    "url": ai_url,
                    "title": f"Google AI Overview: {query}",
                    "description": ai_snippets[0][:300],
                    "text": "\n\n".join(ai_snippets),
                }
            )

        organic = data.get("organic") or data.get("oragnic") or []
        for entry in organic:
            if not isinstance(entry, dict):
                continue
            url = entry.get("link", "")
            title = entry.get("title", "")
            description = entry.get("description", "") or ""
            if not url:
                continue
            results.append(
                {
                    "url": url,
                    "title": title,
                    "description": description,
                }
            )
            if len(results) >= max_results:
                break

        return results[:max_results]
    except Exception as e:
        return [{"error": f"Bright Data search error: {str(e)}"}]


async def brightdata_unlock_url(
    url: str,
    max_length: int = 10000,
    data_format: str = "markdown",
) -> str:
    """
    Fetch and unlock a URL using Bright Data Unlocker API.

    Supports anti-bot bypass, markdown conversion, and automatic proxy management.
    Returns content as markdown or raw HTML depending on data_format parameter.

    Args:
        url: The URL to fetch
        max_length: Maximum length of returned content (chars)
        data_format: "markdown" (clean text) or "raw" (HTML)

    Returns:
        The page content as a string, or error message if failed.
    """
    if not BRIGHTDATA_API_KEY:
        return "Error: BRIGHTDATA_API_KEY required for Bright Data Unlocker. Set it in .env"
    if not BRIGHTDATA_UNLOCKER_ZONE:
        return "Error: BRIGHTDATA_UNLOCKER_ZONE required for Bright Data Unlocker. Set it in .env"

    payload = {
        "zone": BRIGHTDATA_UNLOCKER_ZONE,
        "url": url,
        "format": "json",
        "data_format": data_format,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                BRIGHTDATA_REQUEST_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    return f"Error: Bright Data Unlocker HTTP {response.status}: {text[:300]}"

                data = await response.json()
                body = data.get("body", "")

                if not body:
                    return f"Error: Empty response from {url}"

                # Trim to max_length if needed
                if len(body) > max_length:
                    body = body[:max_length] + f"\n\n[Content truncated at {max_length} characters]"

                return body

    except asyncio.TimeoutError:
        return f"Error: Timeout fetching {url} (120 seconds)"
    except Exception as e:
        return f"Error: Failed to fetch {url} with Bright Data Unlocker: {str(e)}"
