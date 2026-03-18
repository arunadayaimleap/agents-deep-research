#!/usr/bin/env python3
"""
Test free US proxies from us_proxies.json.
Uses requests to verify each proxy can reach lumtest.com/myip.json.
"""
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install: pip install requests")
    sys.exit(1)

PROXIES_JSON = Path(__file__).resolve().parent / "us_proxies.json"
TEST_URL = "http://lumtest.com/myip.json"
TIMEOUT = 10


def load_proxies(limit=20):
    if not PROXIES_JSON.exists():
        print(f"Run fetch_us_proxies.py first to create {PROXIES_JSON}")
        sys.exit(1)
    data = json.loads(PROXIES_JSON.read_text(encoding="utf-8"))
    return data["proxies"][:limit]


def test_proxy(proxy_url):
    try:
        r = requests.get(TEST_URL, proxies={"http": proxy_url, "https": proxy_url}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, default=10, help="Number of proxies to test (default 10)")
    args = p.parse_args()

    proxies = load_proxies(limit=args.n)
    print(f"=== Testing {len(proxies)} US proxies ===\n")
    print(f"Test URL: {TEST_URL}\n")

    working = []
    for i, p in enumerate(proxies, 1):
        url = p["url"]
        print(f"[{i}/{len(proxies)}] {url} ... ", end="", flush=True)
        result = test_proxy(url)
        if "error" in result:
            print(f"FAIL: {result['error'][:50]}")
        else:
            ip = result.get("ip", "?")
            cc = result.get("geo", {}).get("country_code", "?")
            print(f"OK -> IP: {ip} ({cc})")
            working.append({"url": url, "ip": ip, "country": cc})

    print(f"\n=== Summary: {len(working)}/{len(proxies)} working ===")
    if working:
        print("Working proxies:")
        for w in working[:5]:
            print(f"  {w['url']} -> {w['ip']} ({w['country']})")
    return 0 if working else 1


if __name__ == "__main__":
    sys.exit(main())
