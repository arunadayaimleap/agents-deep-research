#!/usr/bin/env python3
"""
Test: Extract prices from URLs using Kameleo + optional free US proxy rotation.

Usage:
  python test_batch_prices_kameleo_proxy.py       # 5 URLs, with proxy rotation
  python test_batch_prices_kameleo_proxy.py -n 3 # 3 URLs
  python test_batch_prices_kameleo_proxy.py --no-proxy  # Kameleo only (no proxy)

Requires:
- Kameleo running (kameleo start)
- urls-mixed.xlsx in project root
- us_proxies.json (run fetch_us_proxies.py) for proxy rotation
"""
import json
import re
import time
import random
import time
from pathlib import Path

# Add project root
_project_root = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(_project_root))

PROXIES_JSON = _project_root / "us_proxies.json"


def load_proxies():
    """Load free US proxies from us_proxies.json. Returns list of {ip, port, url}."""
    if not PROXIES_JSON.exists():
        return []
    data = json.loads(PROXIES_JSON.read_text(encoding="utf-8"))
    proxies = data.get("proxies", [])
    random.shuffle(proxies)  # Rotate order
    return proxies


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


def _is_proxy_error(err: str) -> bool:
    """True if error indicates proxy failure (rotate to next)."""
    err_lower = err.lower()
    return (
        "503" in err_lower or "external ip" in err_lower or "proxy" in err_lower
        or "ip_forbidden" in err_lower or "connection" in err_lower
    )


def _cleanup_kameleo_profiles(verbose: bool = False):
    """Stop and delete all Kameleo profiles to free 'Concurrent browsers limit exceeded'."""
    try:
        from kameleo.local_api_client import KameleoLocalApiClient
        client = KameleoLocalApiClient(endpoint='http://localhost:5050')
        profiles = client.profile.list_profiles()
        for p in profiles:
            try:
                client.profile.stop_profile(p.id)
            except Exception:
                pass
            try:
                client.profile.delete_profile(p.id)
            except Exception:
                pass
        if verbose and profiles:
            print(f"      [verbose] Cleaned up {len(profiles)} stray Kameleo profile(s)")
    except Exception as e:
        if verbose:
            print(f"      [verbose] Cleanup: {e}")


def fetch_and_extract_price(url: str, proxy_list: list | None = None, verbose: bool = False) -> dict:
    """Fetch page via Kameleo, extract title + prices. Rotates through proxy_list on proxy failures."""
    from kameleo.local_api_client import KameleoLocalApiClient
    from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference, ProxyChoice, Server
    from playwright.sync_api import sync_playwright

    def _log(msg: str):
        if verbose:
            print(f"      [verbose] {msg}")

    client = KameleoLocalApiClient(endpoint='http://localhost:5050')
    fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
    if not fps:
        return {"url": url, "error": "No Kameleo fingerprints"}

    proxies = proxy_list or [None]  # None = no proxy
    last_error = None
    total = len(proxies)

    for idx, proxy in enumerate(proxies):
        profile = None
        proxy_desc = proxy["url"] if proxy else "direct"
        _log(f"proxy [{idx+1}/{total}] {proxy_desc}")
        try:
            create_kw = dict(fingerprint_id=fps[0].id, name='batch-price')
            if proxy:
                create_kw["proxy"] = ProxyChoice(
                    value='http',
                    extra=Server(host=proxy["ip"], port=proxy["port"]),
                )
            profile = client.profile.create_profile(CreateProfileRequest(**create_kw))

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
            try:
                client.profile.delete_profile(profile.id)
            except Exception:
                pass

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

            _log(f"proxy [{idx+1}/{total}] OK")
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
            last_error = str(e)
            _log(f"proxy [{idx+1}/{total}] FAIL: {last_error[:80]}")
            if profile:
                try:
                    client.profile.stop_profile(profile.id)
                except Exception:
                    pass
                try:
                    client.profile.delete_profile(profile.id)
                except Exception:
                    pass
                time.sleep(3)  # Let Kameleo release before next profile
            if proxy_list and _is_proxy_error(last_error):
                _log("rotating to next proxy...")
                continue  # Try next proxy
            break

    return {"url": url, "error": last_error or "Unknown error", "main_price": None}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract prices via Kameleo + optional proxy rotation")
    parser.add_argument("-n", type=int, default=5, help="Number of URLs to test (default 5)")
    parser.add_argument("--no-proxy", action="store_true", help="Skip proxy, use Kameleo direct connection")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose: show proxy attempts and rotation")
    args = parser.parse_args()

    proxy_list = None
    if not args.no_proxy and PROXIES_JSON.exists():
        data = json.loads(PROXIES_JSON.read_text(encoding="utf-8"))
        proxy_list = data.get("proxies", [])
        random.shuffle(proxy_list)
        print(f"[*] Loaded {len(proxy_list)} US proxies for rotation\n")
    elif not args.no_proxy:
        print("[*] us_proxies.json not found - run fetch_us_proxies.py. Using direct connection.\n")
    else:
        print("[*] Using Kameleo (direct connection, --no-proxy)\n")

    print("=== Kameleo - Batch Price Extraction ===\n")

    _cleanup_kameleo_profiles(verbose=args.verbose)
    import time
    time.sleep(2)  # Let Kameleo release resources after cleanup

    xlsx_path = _project_root / "urls-mixed.xlsx"
    if not xlsx_path.exists():
        print(f"[ERROR] File not found: {xlsx_path}")
        return 1

    urls = load_urls_from_xlsx(str(xlsx_path), n=args.n, random_sample=True)
    print(f"[*] Loaded {len(urls)} random URLs from urls-mixed.xlsx\n")

    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url[:70]}...")
        r = fetch_and_extract_price(url, proxy_list, verbose=args.verbose)
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
