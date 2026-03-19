#!/usr/bin/env python3
"""
Runner: Playwright + GeoNode proxy, random URLs from Excel.

Usage:
  python run_playwright_proxy.py       # 5 random URLs
  python run_playwright_proxy.py -n 10 # 10 random URLs

Requires:
- urls-mixed.xlsx in project root
- geonode_us_proxy.json (run find_geonode_us_proxy.py)
"""
import argparse
import json
import re
import random
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PROXY_JSON = PROJECT_ROOT / "geonode_us_proxy.json"
XLSX_PATH = PROJECT_ROOT / "urls-mixed.xlsx"


def load_proxy() -> str | None:
    """Load proxy URL from geonode_us_proxy.json."""
    if not PROXY_JSON.exists():
        return None
    data = json.loads(PROXY_JSON.read_text(encoding="utf-8"))
    return data.get("url")


def load_urls_from_xlsx(path: Path, n: int = 5, random_sample: bool = True) -> list[str]:
    """Load URLs from xlsx. Returns only valid URLs (http/https)."""
    import pandas as pd
    df = pd.read_excel(path, header=None)
    urls = []
    for _, row in df.iterrows():
        val = str(row.iloc[0]).strip() if len(row) > 0 else ""
        if not val:
            continue
        if re.match(r"^[a-zA-Z0-9-]+\.(com|org|net|io|co|ae)[/\w\-\.\?\=\&\%\#]*", val):
            val = "https://" + val
        if val.startswith("http://") or val.startswith("https://"):
            urls.append(val)
    if random_sample and len(urls) > n:
        return random.sample(urls, n)
    return urls[:n]


def extract_prices_from_html(html: str) -> list[str]:
    """Extract price strings from HTML."""
    price_pattern = r'.{0,50}([\$€£¥₹]\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*[\$€£¥₹]).{0,50}'
    matches = re.finditer(price_pattern, html, re.DOTALL)
    seen = set()
    prices = []
    for m in matches:
        p = m.group(1).strip()
        if p and p not in seen:
            seen.add(p)
            prices.append(p)
    # Sort by numeric value (desc)
    def to_float(s):
        try:
            return float(re.sub(r'[^\d.]', '', s)) if re.search(r'\d', s) else 0
        except (ValueError, TypeError):
            return 0
    prices.sort(key=to_float, reverse=True)
    return prices


def fetch_url(url: str, proxy_url: str) -> dict:
    """Fetch URL with Playwright + proxy. Returns {status, title, main_price, prices, error}."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy={"server": proxy_url})
            page = browser.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            status = response.status if response else 0
            html = page.content()
            title = page.title()
            browser.close()

        prices = extract_prices_from_html(html)
        main = None
        for p in prices:
            try:
                v = float(re.sub(r'[^\d.]', '', p))
                if v > 1:
                    main = p
                    break
            except (ValueError, TypeError):
                pass
        main = main or (prices[0] if prices else None)

        return {"status": status, "title": title, "main_price": main, "prices": prices[:10], "error": None}
    except Exception as e:
        return {"status": 0, "title": "", "main_price": None, "prices": [], "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Playwright + proxy batch runner")
    parser.add_argument("-n", type=int, default=5, help="Number of random URLs (default 5)")
    args = parser.parse_args()

    proxy_url = load_proxy()
    if not proxy_url:
        print("[ERROR] geonode_us_proxy.json not found. Run: python find_geonode_us_proxy.py")
        return 1

    if not XLSX_PATH.exists():
        print(f"[ERROR] {XLSX_PATH} not found")
        return 1

    urls = load_urls_from_xlsx(XLSX_PATH, n=args.n, random_sample=True)
    print(f"[*] Proxy: {proxy_url}")
    print(f"[*] Loaded {len(urls)} random URLs from urls-mixed.xlsx\n")
    print("=" * 70)

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] {url[:65]}...")
        r = fetch_url(url, proxy_url)
        if r["error"]:
            print(f"    [FAIL] {r['error']}")
        else:
            print(f"    [OK] Status={r['status']} | Title: {r['title'][:45]}...")
            print(f"    Price: {r['main_price'] or '(none)'}")

    print("\n" + "=" * 70)
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
