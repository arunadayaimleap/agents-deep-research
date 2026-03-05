#!/usr/bin/env python3
"""
Test script for BrightData SERP API (Google Search with AI Overview).

The API returns a large JSON with these key sections:
  - general: query metadata (language, location, timestamp)
  - organic[]: standard search results (link, title, description, snippet)
  - ai_overview: Google AI Overview (texts[], references[])
  - people_also_ask[]: PAA questions with answers
  - shopping[]: shopping results with prices
  - perspectives[]: forum/social perspectives
  - pagination: next page links

IMPORTANT PARSING NOTES:
  - Response format: format="raw" → returns raw HTML, format="json" (via brd_json=1) → returns structured JSON
  - To get JSON: append &brd_json=1 to the Google search URL (NOT to the API payload)
  - Images come as base64 strings — strip them for LLM (very large)
  - There is a typo in the API: "oragnic" (duplicate of "organic") — ignore it
  - Shopping results may have price data: look for shopping[] array
  - For price comparison: use organic[].description + shopping[] results

Usage:
  python test_brightdata_serp.py
  python test_brightdata_serp.py "OnePlus Nord Buds 3r price site:flipkart.com"
  python test_brightdata_serp.py "Whirlpool J3KHVG33QL microwave price" us
"""
import asyncio
import json
import os
import re
import ssl
import sys
import aiohttp
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")
# The SERP zone name — check your BrightData dashboard
# From get_active_zones: zone names include 'serp' type zones
BRIGHTDATA_SERP_ZONE = os.getenv("BRIGHTDATA_SERP_ZONE", "serp")
BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def strip_base64_images(obj):
    """Recursively strip base64 image strings from parsed JSON to reduce noise."""
    if isinstance(obj, dict):
        return {
            k: strip_base64_images(v) for k, v in obj.items()
            if k not in ("icon", "image_base64", "image") or not (isinstance(v, str) and v.startswith("data:image"))
        }
    elif isinstance(obj, list):
        return [strip_base64_images(i) for i in obj]
    return obj


def extract_llm_payload(data: dict) -> dict:
    """
    Strip noise from the raw SERP JSON and return a clean payload for LLM analysis.
    Keeps: general, organic (with link/title/description), ai_overview texts,
    people_also_ask answers, shopping results (for prices), perspectives.
    Strips: all base64 images, duplicate 'oragnic' field, raw HTML in answer_html.
    """
    clean = {}

    # General metadata
    if "general" in data:
        clean["general"] = data["general"]

    # Organic results — most useful for finding product URLs
    if "organic" in data:
        clean["organic"] = [
            {
                "rank": r.get("rank"),
                "link": r.get("link"),
                "source": r.get("source"),
                "title": r.get("title"),
                "description": r.get("description"),
                "snippet_highlighted_words": r.get("snippet_highlighted_words", []),
            }
            for r in data.get("organic", [])
        ]

    # AI Overview — often has direct answers with prices
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

    # People Also Ask — may contain price info
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

    # Shopping results — direct price data!
    if "shopping" in data:
        clean["shopping"] = [
            {
                "title": s.get("title"),
                "link": s.get("link"),
                "source": s.get("source"),
                "price": s.get("price"),
                "currency": s.get("currency"),
                "rating": s.get("rating"),
                "reviews_cnt": s.get("reviews_cnt"),
            }
            for s in data.get("shopping", [])
        ]

    # Perspectives — social/forum posts
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


async def serp_search(query: str, country: str = "us", gl: str = None, hl: str = "en") -> dict:
    """Run a Google search via BrightData SERP API and return parsed JSON."""
    if not BRIGHTDATA_API_KEY:
        print("ERROR: BRIGHTDATA_API_KEY not set")
        sys.exit(1)

    # Map country to gl (Google geolocation) param if not specified
    country_to_gl = {
        "us": "US", "in": "IN", "gb": "GB", "au": "AU",
        "ca": "CA", "de": "DE", "fr": "FR", "ae": "AE",
    }
    gl = gl or country_to_gl.get(country.lower(), "US")

    # Build Google search URL with brd_json=1 (structured JSON response)
    # brd_ai_overview=2 adds AI Overview (5-10s extra latency)
    encoded_query = quote_plus(query)
    search_url = (
        f"https://www.google.com/search?q={encoded_query}"
        f"&gl={gl}&hl={hl}&brd_json=1&brd_ai_overview=2"
    )

    payload = {
        "zone": BRIGHTDATA_SERP_ZONE,
        "url": search_url,
        "format": "raw",  # 'raw' because brd_json=1 in URL handles JSON parsing
    }

    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"Query      : {query}")
    print(f"Country/GL : {country}/{gl}")
    print(f"Zone       : {BRIGHTDATA_SERP_ZONE}")
    print(f"Search URL : {search_url[:120]}...")
    print("-" * 60)

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(
            BRIGHTDATA_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            print(f"HTTP Status: {resp.status}")
            raw = await resp.text()

            if resp.status != 200:
                print(f"Error: {raw[:1000]}")
                return {}

            # The response is raw text — parse JSON
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                print(f"Raw (first 2000 chars): {raw[:2000]}")
                return {}

            return data


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "OnePlus Nord Buds 3r price site:flipkart.com"
    country = sys.argv[2] if len(sys.argv) > 2 else "in"

    data = await serp_search(query, country)
    if not data:
        print("No data returned.")
        return

    # Show raw structure keys
    print(f"\nTop-level keys: {list(data.keys())}")

    # Save full raw response for inspection
    raw_path = Path("/tmp/serp_raw.json")
    raw_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Full raw JSON saved to: {raw_path}")

    # Extract clean LLM payload
    clean = extract_llm_payload(data)
    clean_path = Path("/tmp/serp_clean.json")
    clean_path.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Clean LLM payload saved to: {clean_path}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"ORGANIC RESULTS ({len(clean.get('organic', []))} found):")
    for r in clean.get("organic", [])[:5]:
        print(f"  [{r['rank']}] {r['title']}")
        print(f"       {r['link']}")
        print(f"       {r['description'][:120] if r.get('description') else 'N/A'}...")

    if clean.get("shopping"):
        print(f"\nSHOPPING RESULTS ({len(clean['shopping'])} found) — PRICE DATA:")
        for s in clean["shopping"][:5]:
            print(f"  {s['title'][:60]} | {s.get('currency','')}{s.get('price','N/A')} | {s['source']} | {s['link'][:80]}")

    if clean.get("ai_overview"):
        print(f"\nAI OVERVIEW:")
        for t in clean["ai_overview"]["texts"][:3]:
            if t.get("snippet"):
                print(f"  {t['snippet'][:200]}")

    clean_json_str = json.dumps(clean, indent=2, ensure_ascii=False)
    print(f"\nClean payload size: {len(clean_json_str)} chars (suitable for LLM context)")


if __name__ == "__main__":
    asyncio.run(main())
