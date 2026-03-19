#!/usr/bin/env python3
"""
Test Playwright with GeoNode US proxy (no Kameleo).

Usage: python test_playwright_proxy.py [url]

Default URL: http://lumtest.com/myip.json
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PROXY_JSON = PROJECT_ROOT / "geonode_us_proxy.json"
DEFAULT_URL = "http://lumtest.com/myip.json"


def load_proxy():
    """Load proxy from geonode_us_proxy.json. Returns proxy URL or None."""
    if not PROXY_JSON.exists():
        return None
    data = json.loads(PROXY_JSON.read_text(encoding="utf-8"))
    return data.get("url")


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    proxy_url = load_proxy()
    if not proxy_url:
        print("[ERROR] geonode_us_proxy.json not found. Run: python find_geonode_us_proxy.py")
        return 1

    print(f"[*] Proxy: {proxy_url}")
    print(f"[*] URL:   {url}\n")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy={"server": proxy_url})
        page = browser.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = response.status if response else 0
            body = page.content()
            browser.close()

            print(f"[OK] Status: {status}")
            if "myip" in url or "ip" in url.lower():
                # Try to extract JSON body from page
                import re
                m = re.search(r"<pre[^>]*>(.*?)</pre>", body, re.DOTALL)
                if m:
                    print(f"[OK] Response: {m.group(1).strip()[:200]}")
                else:
                    print(f"[OK] Body: {body[:300]}...")
            else:
                title = page.title() if hasattr(page, "title") else ""
                print(f"[OK] Title: {title[:60]}...")
                print(f"[OK] Body length: {len(body)} chars")
        except Exception as e:
            browser.close()
            print(f"[FAIL] {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
