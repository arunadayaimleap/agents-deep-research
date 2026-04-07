import os
import asyncio
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

    print(f"\n[SERP] Bright Data search query: {query}", flush=True)

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
                    err = [{"error": f"Bright Data search HTTP {response.status}: {text[:300]}"}]
                    print(f"[SERP] Error: HTTP {response.status}", flush=True)
                    return err
                
                try:
                    data = await response.json()
                except Exception as json_err:
                    # Response was 200 but not valid JSON - might be security check or rate limit
                    content_type = response.headers.get('content-type', 'unknown')
                    text = await response.text()
                    error_detail = f"Got HTTP 200 but invalid JSON. Content-Type: {content_type}. Response: {text[:200]}"
                    print(f"[BRIGHTDATA] Error: {error_detail}")
                    return [{"error": f"Bright Data API error (rate limited or security check): {error_detail}"}]

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

        out = results[:max_results]
        print(f"[SERP] Returned {len(out)} result(s)", flush=True)
        return out
    except Exception as e:
        print(f"[SERP] Exception: {e}", flush=True)
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

    print(f"[CRAWL] Fetching URL: {url}")
    
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
                    error_msg = f"Error: Bright Data Unlocker HTTP {response.status}: {text[:300]}"
                    print(f"[CRAWL] {error_msg}")
                    return error_msg

                data = await response.json()
                body = data.get("body", "")

                if not body:
                    error_msg = f"Error: Empty response from {url}"
                    print(f"[CRAWL] {error_msg}")
                    return error_msg

                # Trim to max_length if needed
                if len(body) > max_length:
                    body = body[:max_length] + f"\n\n[Content truncated at {max_length} characters]"

                print(f"[CRAWL] Successfully fetched {len(body)} characters from {url}")
                print(f"[CRAWL] Content preview: {body[:150]}...\n")
                return body

    except asyncio.TimeoutError:
        error_msg = f"Error: Timeout fetching {url} (120 seconds)"
        print(f"[CRAWL] {error_msg}\n")
        return error_msg
    except Exception as e:
        error_msg = f"Error: Failed to fetch {url} with Bright Data Unlocker: {str(e)}"
        print(f"[CRAWL] {error_msg}\n")
        return error_msg
