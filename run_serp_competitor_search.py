#!/usr/bin/env python3
"""
Bright Data SERP competitor search: for each URL, find competitor product URLs
by searching with the exact model name.

Research summary:
- Bright Data SERP API has NO batch mode (multi param deprecated Dec 2025).
- Rate limiting: Bright Data uses rotating IPs; recommend 1.5-2s delay between
  requests to avoid hammering. Sequential is safest for ~98 requests.
- API: POST https://api.brightdata.com/request with zone, url, format=json

Usage:
  python run_serp_competitor_search.py              # all 98 URLs
  python run_serp_competitor_search.py -n 3       # test with 3 URLs

Requires:
- BRIGHTDATA_API_KEY, BRIGHTDATA_SERP_ZONE in .env
- urls_extracted.json (from extract_urls_from_xlsx.py)
- zyte_results_*.json (optional, for better model names from Zyte product extraction)
"""
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent

# E-commerce domains that are likely product pages (competitors)
ECOMMERCE_DOMAINS = {
    "amazon.com", "amazon.", "walmart.com", "ebay.com", "ebay.", "target.com",
    "bestbuy.com", "homedepot.com", "lowes.com", "acehardware.com",
    "grainger.com", "bhphotovideo.com", "costco.com", "etsy.com", "depop.com",
    "poshmark.com", "alibaba.com", "thredup.com", "sephora.com", "sephora.com.au",
    "barnesandnoble.com", "chewy.com", "wayfair.com", "overstock.com",
    "newegg.com", "adorama.com", "cdw.com", "staples.com", "officedepot.com",
    "craftsman.com", "papashardware.com", "truevalue.com", "northerntool.com",
    "menards.com", "tractorsupply.com", "blains.com", "ruralking.com",
    "harborfreight.com", "nike.com", "underarmour.com", "adidas.com",
}


def load_dotenv():
    try:
        from dotenv import load_dotenv as _load
        _load(PROJECT_ROOT / ".env")
    except ImportError:
        pass


def url_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        # strip www.
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_ecommerce_product_url(url: str, exclude_domain: str = "") -> bool:
    """Check if URL is from a known e-commerce product domain (and not the source)."""
    domain = url_domain(url)
    if exclude_domain and domain == exclude_domain:
        return False
    for eco in ECOMMERCE_DOMAINS:
        if eco in domain:
            return True
    return False


def build_model_name_map(extracted: dict, zyte_path: Path | None) -> dict[str, str]:
    """
    Build url -> model_name mapping.
    Prefer Zyte product.name when URL matches; else use display_text from extracted.
    """
    url_to_model: dict[str, str] = {}

    # From urls_extracted.json details
    for d in extracted.get("details", []):
        url = d.get("url", "").strip()
        if not url:
            continue
        display = (d.get("display_text") or "").strip()
        # Use display_text up to " - " or " | " as product name
        if display:
            for sep in [" - ", " | ", " – "]:
                if sep in display:
                    display = display.split(sep)[0].strip()
            # Limit length for search query
            if len(display) > 80:
                display = display[:77] + "..."
            if display and not display.startswith("http"):
                url_to_model[url] = display

    # Override with Zyte product names when available
    if zyte_path and zyte_path.exists():
        try:
            data = json.loads(zyte_path.read_text(encoding="utf-8"))
            for r in data.get("results", []):
                if not r.get("success"):
                    continue
                resp = r.get("response", {})
                prod = resp.get("product") or {}
                name = (prod.get("name") or "").strip()
                url = (resp.get("url") or r.get("echoData", {}).get("url") or "").strip()
                if url and name:
                    url_to_model[url] = name[:120]  # prefer Zyte's product name
        except Exception as e:
            print(f"[WARN] Could not load Zyte results: {e}")

    return url_to_model


def brightdata_serp_search(query: str, api_key: str, zone: str, country: str = "us") -> dict | None:
    """
    Call Bright Data SERP API (sync). Returns full JSON or None on error.
    Uses exact phrase search: "query"
    Per Bright Data docs: brd_json=json in URL for structured JSON, format=raw for response body.
    """
    import urllib.request

    search_url = f"https://www.google.com/search?q={quote(query)}&gl={country}&hl=en&brd_json=json"
    payload = {
        "zone": zone,
        "url": search_url,
        "format": "raw",
        "country": country,
    }
    req = urllib.request.Request(
        "https://api.brightdata.com/request",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [ERR] {str(e)[:100]}")
        return None


def extract_competitor_urls(serp_data: dict, source_url: str, max_results: int = 15) -> list[dict]:
    """Extract competitor product URLs from SERP organic results."""
    source_domain = url_domain(source_url)
    competitors = []
    organic = serp_data.get("organic") or serp_data.get("oragnic") or []
    for entry in organic:
        if not isinstance(entry, dict):
            continue
        link = entry.get("link") or entry.get("url") or ""
        if not link or not is_ecommerce_product_url(link, exclude_domain=source_domain):
            continue
        competitors.append({
            "url": link,
            "title": (entry.get("title") or "")[:200],
            "rank": entry.get("rank") or entry.get("global_rank") or len(competitors) + 1,
        })
        if len(competitors) >= max_results:
            break
    return competitors


def main():
    load_dotenv()
    api_key = os.getenv("BRIGHTDATA_API_KEY")
    zone = os.getenv("BRIGHTDATA_SERP_ZONE") or "serp_api1"
    if not api_key:
        print("[ERROR] BRIGHTDATA_API_KEY not found in .env")
        return 1

    parser = argparse.ArgumentParser(description="Bright Data SERP competitor search")
    parser.add_argument("-n", type=int, default=None, help="Limit to N URLs (default: all)")
    parser.add_argument("--delay", type=float, default=1.8, help="Delay between requests in seconds (default 1.8)")
    parser.add_argument("--extracted", type=str, default=None, help="Path to urls_extracted.json")
    parser.add_argument("--zyte", type=str, default=None, help="Path to zyte results JSON")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--debug", action="store_true", help="Save raw SERP response for first request to serp_debug.json")
    args = parser.parse_args()

    extracted_path = Path(args.extracted) if args.extracted else PROJECT_ROOT / "urls_extracted.json"
    if not extracted_path.exists():
        print(f"[ERROR] {extracted_path} not found. Run extract_urls_from_xlsx.py first.")
        return 1

    # Find latest Zyte results if not specified
    zyte_path = Path(args.zyte) if args.zyte else None
    if not zyte_path:
        for f in sorted(PROJECT_ROOT.glob("zyte_results_*.json"), reverse=True):
            zyte_path = f
            break

    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    url_to_model = build_model_name_map(extracted, zyte_path)

    urls = extracted.get("urls", [])
    if args.n:
        urls = urls[: args.n]

    output_path = Path(args.output) if args.output else PROJECT_ROOT / f"competitor_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print("[*] Bright Data SERP competitor search")
    print(f"[*] URLs: {len(urls)} | delay: {args.delay}s | zone: {zone}")
    print(f"[*] Output: {output_path}\n")

    results = []
    for i, url in enumerate(urls):
        model_name = url_to_model.get(url)
        if not model_name:
            print(f"  [{i+1}/{len(urls)}] SKIP - no model name for {url[:60]}...")
            results.append({
                "source_url": url,
                "model_name": None,
                "search_query": None,
                "competitors": [],
                "error": "no_model_name",
            })
            continue

        # Exact phrase search for same model
        search_query = f'"{model_name}"'
        print(f"  [{i+1}/{len(urls)}] Searching: {model_name[:50]}...")

        serp = brightdata_serp_search(search_query, api_key, zone)
        if args.debug and serp:
            debug_path = PROJECT_ROOT / "serp_debug.json"
            debug_path.write_text(json.dumps({"query": search_query, "response": serp}, indent=2, default=str), encoding="utf-8")
            print(f"       [DEBUG] Saved raw SERP to {debug_path}")
            # Show first 5 organic domains for debugging
            organic = serp.get("organic") or serp.get("oragnic") or []
            for j, e in enumerate(organic[:5]):
                link = (e.get("link") or e.get("url") or "")
                print(f"       [DEBUG] organic[{j}] {url_domain(link)}: {link[:70]}...")
        if not serp:
            results.append({
                "source_url": url,
                "model_name": model_name,
                "search_query": search_query,
                "competitors": [],
                "error": "serp_request_failed",
            })
            time.sleep(args.delay)
            continue

        competitors = extract_competitor_urls(serp, url)
        results.append({
            "source_url": url,
            "model_name": model_name,
            "search_query": search_query,
            "competitors": competitors,
            "competitor_count": len(competitors),
        })
        print(f"       -> {len(competitors)} competitor URLs")

        time.sleep(args.delay)

    output = {
        "metadata": {
            "total_searched": len(urls),
            "delay_seconds": args.delay,
            "zone": zone,
            "timestamp": datetime.now().isoformat(),
        },
        "results": results,
    }

    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n[OK] Saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
