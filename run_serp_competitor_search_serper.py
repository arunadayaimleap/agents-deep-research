#!/usr/bin/env python3
"""
Serper.dev SERP competitor search: for each URL, find competitor product URLs
by searching with the exact model name.

Uses Serper.dev API - simpler, faster, and cheaper than Bright Data for SERP.
- POST https://google.serper.dev/search with {"q": query}
- X-API-KEY header for auth
- Returns organic results with link, title, snippet, position
- High rate limits (free tier: 2500/mo; paid: 300 qps)

Usage:
  python run_serp_competitor_search_serper.py              # all 98 URLs
  python run_serp_competitor_search_serper.py -n 5       # test with 5 URLs

Requires:
- SERPER_API_KEY in .env
- urls_extracted.json (from extract_urls_from_xlsx.py)
- zyte_results_*.json (optional, for better model names)
"""
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

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
    """Build url -> model_name mapping from extracted + Zyte."""
    url_to_model: dict[str, str] = {}

    for d in extracted.get("details", []):
        url = d.get("url", "").strip()
        if not url:
            continue
        display = (d.get("display_text") or "").strip()
        if display:
            for sep in [" - ", " | ", " – "]:
                if sep in display:
                    display = display.split(sep)[0].strip()
            if len(display) > 80:
                display = display[:77] + "..."
            if display and not display.startswith("http"):
                url_to_model[url] = display

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
                    url_to_model[url] = name[:120]
        except Exception as e:
            print(f"[WARN] Could not load Zyte results: {e}")

    return url_to_model


def serper_search(query: str, api_key: str, num: int = 20) -> dict | None:
    """
    Call Serper.dev search API. Returns full JSON or None on error.
    """
    import urllib.request

    payload = {"q": query, "num": num}
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [ERR] {str(e)[:100]}")
        return None


def extract_competitor_urls(serp_data: dict, source_url: str, max_results: int = 15) -> list[dict]:
    """Extract competitor product URLs from Serper organic results."""
    source_domain = url_domain(source_url)
    competitors = []
    organic = serp_data.get("organic") or []
    for entry in organic:
        if not isinstance(entry, dict):
            continue
        link = entry.get("link") or entry.get("url") or ""
        if not link or not is_ecommerce_product_url(link, exclude_domain=source_domain):
            continue
        rank = entry.get("position") or entry.get("rank") or len(competitors) + 1
        competitors.append({
            "url": link,
            "title": (entry.get("title") or "")[:200],
            "rank": rank,
        })
        if len(competitors) >= max_results:
            break
    return competitors


def main():
    load_dotenv()
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("[ERROR] SERPER_API_KEY not found in .env")
        return 1

    parser = argparse.ArgumentParser(description="Serper.dev SERP competitor search")
    parser.add_argument("-n", type=int, default=None, help="Limit to N URLs (default: all)")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between requests in seconds (default 0.4)")
    parser.add_argument("--extracted", type=str, default=None, help="Path to urls_extracted.json")
    parser.add_argument("--zyte", type=str, default=None, help="Path to zyte results JSON")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--debug", action="store_true", help="Save raw SERP for first request")
    args = parser.parse_args()

    extracted_path = Path(args.extracted) if args.extracted else PROJECT_ROOT / "urls_extracted.json"
    if not extracted_path.exists():
        print(f"[ERROR] {extracted_path} not found. Run extract_urls_from_xlsx.py first.")
        return 1

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

    output_path = Path(args.output) if args.output else PROJECT_ROOT / f"competitor_urls_serper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print("[*] Serper.dev SERP competitor search")
    print(f"[*] URLs: {len(urls)} | delay: {args.delay}s | provider: serper")
    print(f"[*] Output: {output_path}\n")

    results = []
    debug_saved = False
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

        # Try exact phrase first; if Serper returns no organic results, retry without quotes
        search_query = f'"{model_name}"'
        print(f"  [{i+1}/{len(urls)}] Searching: {model_name[:50]}...")

        serp = serper_search(search_query, api_key)
        if serp and not (serp.get("organic") or []):
            search_query = model_name
            serp = serper_search(search_query, api_key)
            if serp:
                print(f"       (exact phrase returned 0, retried without quotes)")
        if args.debug and serp and not debug_saved:
            debug_path = PROJECT_ROOT / "serp_debug_serper.json"
            debug_path.write_text(json.dumps({"query": search_query, "response": serp}, indent=2, default=str), encoding="utf-8")
            print(f"       [DEBUG] Saved raw SERP to {debug_path}")
            organic = serp.get("organic") or []
            for j, e in enumerate(organic[:5]):
                link = (e.get("link") or e.get("url") or "")
                print(f"       [DEBUG] organic[{j}] {url_domain(link)}: {link[:70]}...")
            debug_saved = True

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
            "provider": "serper",
            "timestamp": datetime.now().isoformat(),
        },
        "results": results,
    }

    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n[OK] Saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
