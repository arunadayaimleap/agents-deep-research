"""
BrightData SERP tool — fetches Google Search results with AI Overview using BrightData's SERP API.

Use this for:
- Finding the source product URL, specs, and price.
- Identifying competitors.
- Finding the direct product URL and price on a competitor site (requires `site:` operator).

Key features:
- Automatically requests JSON format with AI Overviews enabled.
- Strips large base64 images to keep context sizes manageable.
- Returns a structured JSON payload with organic results, shopping results, AI Overviews, and PAA.
"""
import os
import ssl
import json
import logging
import asyncio
from typing import Optional
from urllib.parse import quote_plus
import aiohttp
from agents import function_tool

logger = logging.getLogger(__name__)

BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def _get_config() -> tuple[str, str]:
    """Return (api_key, zone_name). Raises if key missing."""
    api_key = os.getenv("BRIGHTDATA_API_KEY", "")
    zone = os.getenv("BRIGHTDATA_SERP_ZONE", "serp_api1")
    return api_key, zone

def _extract_llm_payload(data: dict) -> dict:
    """
    Strip noise from the raw SERP JSON and return a clean payload for LLM analysis.
    Keeps: general, organic (with link/title/description), ai_overview texts,
    people_also_ask answers, shopping results (for prices), perspectives.
    Strips: all base64 images, duplicate 'oragnic' field, raw HTML.
    """
    clean = {}

    if "general" in data:
        clean["general"] = data["general"]

    if "organic" in data:
        clean["organic"] = [
            {
                "rank": r.get("rank"),
                "link": r.get("link"),
                "source": r.get("source"),
                "title": r.get("title"),
                "description": r.get("description"),
            }
            for r in data.get("organic", [])
        ]

    if "ai_overview" in data:
        ao = data["ai_overview"]
        clean["ai_overview"] = {
            "texts": [
                {
                    "type": t.get("type"),
                    "snippet": t.get("snippet"),
                    "title": t.get("title"),
                    "list": [{"snippet": i.get("snippet")} for i in t.get("list", [])] if "list" in t else None,
                }
                for t in ao.get("texts", [])
            ],
            "references": [
                {"href": r.get("href"), "title": r.get("title"), "source": r.get("source")}
                for r in ao.get("references", [])
            ]
        }

    if "people_also_ask" in data:
        clean["people_also_ask"] = [
            {
                "question": q.get("question"),
                "answers": [
                    a.get("value", {}).get("text", "") if isinstance(a.get("value"), dict) else ""
                    for a in q.get("answers", [])
                ]
            }
            for q in data.get("people_also_ask", [])
        ]

    if "shopping" in data:
        clean["shopping"] = [
            {
                "title": s.get("title"),
                "link": s.get("link"),
                "source": s.get("source"),
                "price": s.get("price"),
                "currency": s.get("currency"),
                "rating": s.get("rating"),
            }
            for s in data.get("shopping", [])
        ]

    if "perspectives" in data:
        clean["perspectives"] = [
            {
                "title": p.get("title"),
                "source": p.get("source"),
                "date": p.get("date"),
                "link": p.get("link"),
            }
            for p in data.get("perspectives", [])
        ]

    return clean

@function_tool
async def brightdata_serp_search(query: str, country: Optional[str] = "us") -> str:
    """
    Perform a Google search using BrightData's SERP API, which includes AI Overviews, Organic Results, and Shopping prices.
    Returns the complete structured JSON response (cleaned of heavy image data) so you can analyze all result snippets to find prices, URLs, and product matches.

    Args:
        query: The exact Google search query. E.g. "OnePlus Nord Buds 3r price site:flipkart.com"
        country: Optional ISO country code for geolocation (e.g., "us", "in", "gb"). Defaults to "us".
    """
    if not query:
        return json.dumps({"error": "Empty query provided."})

    api_key, zone = _get_config()
    if not api_key:
        return json.dumps({"error": "BRIGHTDATA_API_KEY not set in environment."})
        
    country_to_gl = {
        "us": "US", "in": "IN", "gb": "GB", "au": "AU",
        "ca": "CA", "de": "DE", "fr": "FR", "ae": "AE",
    }
    gl = country_to_gl.get(country.lower(), "US")
    hl = "en"

    encoded_query = quote_plus(query)
    search_url = (
        f"https://www.google.com/search?q={encoded_query}"
        f"&gl={gl}&hl={hl}&brd_json=1&brd_ai_overview=2"
    )

    payload = {
        "zone": zone,
        "url": search_url,
        "format": "raw",
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                BRIGHTDATA_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                raw = await response.text()

                if response.status != 200:
                    return json.dumps({"error": f"HTTP {response.status}", "details": raw[:500]})

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return json.dumps({"error": "Failed to parse JSON", "raw_sample": raw[:500]})

                clean_data = _extract_llm_payload(data)
                return json.dumps(clean_data, ensure_ascii=False)

    except Exception as e:
        logger.exception("BrightData SERP API request failed")
        return json.dumps({"error": f"Exception: {str(e)}"})
