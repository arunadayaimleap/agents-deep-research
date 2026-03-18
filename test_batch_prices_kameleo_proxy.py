#!/usr/bin/env python3
"""
Test: Extract prices from URLs using Kameleo only (no proxy).

Usage:
  python test_batch_prices_kameleo_proxy.py     # 5 URLs
  python test_batch_prices_kameleo_proxy.py -n 3 # 3 URLs

Requires:
- Kameleo running (kameleo start)
- urls-mixed.xlsx in project root
"""
import os
import re
import random
from pathlib import Path

# Add project root
_project_root = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(_project_root))


def load_urls_from_xlsx(path: str, n: int = 5, random_sample: bool = True) -> list[str]:
    """Load URLs from xlsx. Column can have URLs or product names. Returns only valid URLs."""
    import pandas as pd
    df = pd.read_excel(path, header=None)
    urls = []
    for _, row in df.iterrows():
        val = str(row.iloc[0]).strip() if len(row) > 0 else ""
        if not val:
            continue
        # Normalize: add https if missing
        if re.match(r"^[a-zA-Z0-9-]+\.(com|org|net|io|co|ae)[/\w\-\.\?\=\&\%\#]*", val):
            val = "https://" + val
        if val.startswith("http://") or val.startswith("https://"):
            urls.append(val)
    if random_sample and len(urls) > n:
        return random.sample(urls, n)
    return urls[:n]


def extract_prices_from_html(html: str) -> list[dict]:
    """Extract prices with context from HTML. Supports $, EUR, GBP, etc."""
    price_pattern = r'.{0,50}([\$€£¥₹]\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*[\$€£¥₹]).{0,50}'
    matches = re.finditer(price_pattern, html, re.DOTALL)

    prices_with_context = []
    for match in matches:
        price = match.group(1).strip()
        if not price:
            continue
        ctx = match.group(0).replace('\n', ' ').replace('\t', ' ')
        ctx = ' '.join(ctx.split())
        prices_with_context.append({"price": price, "context": ctx})

    seen = set()
    unique = []
    for pc in prices_with_context:
        key = (pc["price"], pc["context"])
        if key not in seen:
            seen.add(key)
            unique.append(pc)

    def to_float(p):
        try:
            s = re.sub(r'[^\d.]', '', str(p.get("price", "")))
            return float(s) if s else 0.0
        except (ValueError, TypeError):
            return 0.0

    unique.sort(key=to_float, reverse=True)
    return unique


def fetch_and_extract_price(url: str) -> dict:
    """Fetch page via Kameleo, extract title + prices."""
    from kameleo.local_api_client import KameleoLocalApiClient
    from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference
    from playwright.sync_api import sync_playwright

    client = KameleoLocalApiClient(endpoint='http://localhost:5050')

    fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
    if not fps:
        return {"url": url, "error": "No Kameleo fingerprints"}

    profile = client.profile.create_profile(CreateProfileRequest(
        fingerprint_id=fps[0].id,
        name='batch-price',
    ))

    try:
        client.profile.start_profile(profile.id, BrowserSettings(
            arguments=['mute-audio'],
            preferences=[Preference(key='profile.default_content_settings.images', value=1)],
        ))

        browser_ws = f'ws://localhost:5050/playwright/{profile.id}'
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(endpoint_url=browser_ws)
            context = browser.contexts[0]
            page = context.new_page()

            response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
            status = response.status if response else 0
            page.wait_for_timeout(3000)

            html = page.content()
            title = page.title()

            page.close()
            browser.close()

        client.profile.stop_profile(profile.id)

        prices = extract_prices_from_html(html)
        main_price = None
        if prices:
            significant = []
            for p in prices:
                try:
                    s = re.sub(r'[^\d.]', '', str(p.get("price", "")))
                    if s and float(s) > 1:
                        significant.append(p)
                except (ValueError, TypeError):
                    pass
            main_price = significant[0]["price"] if significant else prices[0]["price"]

        return {
            "url": url,
            "status": status,
            "title": title,
            "main_price": main_price,
            "all_prices": [p["price"] for p in prices[:10]],
            "html_len": len(html),
            "error": None,
        }

    except Exception as e:
        try:
            client.profile.stop_profile(profile.id)
        except Exception:
            pass
        return {"url": url, "error": str(e), "main_price": None}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract prices via Kameleo")
    parser.add_argument("-n", type=int, default=5, help="Number of URLs to test (default 5)")
    args = parser.parse_args()

    print("=== Kameleo - Batch Price Extraction ===\n")
    print("[*] Using Kameleo (direct connection)\n")

    xlsx_path = _project_root / "urls-mixed.xlsx"
    if not xlsx_path.exists():
        print(f"[ERROR] File not found: {xlsx_path}")
        return 1

    urls = load_urls_from_xlsx(str(xlsx_path), n=args.n, random_sample=True)
    print(f"[*] Loaded {len(urls)} random URLs from urls-mixed.xlsx\n")

    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url[:70]}...")
        r = fetch_and_extract_price(url)
        results.append(r)
        if r.get("error"):
            print(f"    [FAIL] {r['error']}")
        else:
            print(f"    [OK] Status={r.get('status')} | Title: {r.get('title','')[:50]}...")
            print(f"    Price: {r.get('main_price') or '(none)'}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in results:
        err = r.get("error")
        price = r.get("main_price") or "-"
        url_short = (r["url"][:55] + "...") if len(r["url"]) > 55 else r["url"]
        status = f"FAIL: {err}" if err else f"OK (price: {price})"
        print(f"  {url_short}")
        print(f"    -> {status}\n")

    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
