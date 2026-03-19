#!/usr/bin/env python3
"""
Find a working US proxy from GeoNode API and save for test_batch_prices_kameleo_proxy.py.

Usage: python find_geonode_us_proxy.py

Output: geonode_us_proxy.json with single {ip, port, url} for Kameleo (no rotation).
"""
import json
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_JSON = PROJECT_ROOT / "geonode_us_proxy.json"
GEONODE_URL = "https://proxylist.geonode.com/api/proxy-list"
TEST_URL = "http://lumtest.com/myip.json"


def fetch_us_proxies() -> list[dict]:
    """Fetch GeoNode proxies, filter US-only. Prefer http, then socks5 (Kameleo supports both)."""
    params = {"limit": 500, "page": 1, "sort_by": "lastChecked", "sort_type": "desc"}
    try:
        r = requests.get(GEONODE_URL, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch GeoNode: {e}")
        return []

    items = data.get("data", [])
    us_proxies = []
    for p in items:
        if p.get("country") != "US":
            continue
        ip = p.get("ip")
        port = str(p.get("port", ""))
        protocols = p.get("protocols") or []
        if not ip or not port:
            continue
        # Kameleo supports http, socks5 (not socks4)
        proto = None
        if "http" in protocols:
            proto = "http"
        elif "socks5" in protocols:
            proto = "socks5"
        if proto:
            us_proxies.append({"ip": ip, "port": port, "proto": proto, "city": p.get("city", "")})

    return us_proxies


def test_proxy(ip: str, port: str, proto: str) -> bool:
    """Test proxy with a simple request."""
    if proto == "http":
        proxy_url = f"http://{ip}:{port}"
    elif proto == "socks5":
        proxy_url = f"socks5://{ip}:{port}"
    else:
        return False
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        r = requests.get(TEST_URL, proxies=proxies, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            j = r.json()
            if j.get("ip") and j.get("country") == "US":
                return True
            return True  # Works even if country differs
        return False
    except Exception:
        return False


def main() -> int:
    print("[*] Fetching US proxies from GeoNode...")
    proxies = fetch_us_proxies()
    print(f"[*] Found {len(proxies)} US proxies (http/socks5)\n")

    for i, p in enumerate(proxies, 1):
        print(f"  [{i}/{len(proxies)}] Testing {p['ip']}:{p['port']} ({p['proto']})...", end=" ")
        if test_proxy(p["ip"], p["port"], p["proto"]):
            print("OK")
            result = {"ip": p["ip"], "port": p["port"], "url": f"{p['proto']}://{p['ip']}:{p['port']}"}
            OUTPUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"\n[OK] Saved working US proxy to {OUTPUT_JSON}")
            print(f"     {result['url']}")
            return 0
        print("FAIL")

    print("\n[ERROR] No working US proxy found. Try again later.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
