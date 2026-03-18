#!/usr/bin/env python3
"""
Test BrightData proxy connectivity (no Kameleo).
Uses requests + proxy to hit lumtest.com/myip.json - BrightData's recommended test.
"""
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

PROXY_URL = os.getenv(
    "BRIGHTDATA_PROXY",
    "http://brd-customer-hl_baa2623c-zone-static:tnej9bv3rk96@brd.superproxy.io:33335",
)


def main():
    import requests

    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    test_url = "http://lumtest.com/myip.json"

    print("=== BrightData Proxy Test ===\n")
    print(f"Proxy: brd.superproxy.io:33335")
    print(f"Test URL: {test_url}\n")

    try:
        r = requests.get(test_url, proxies=proxies, timeout=30)
        r.raise_for_status()
        data = r.json()
        print("[OK] Proxy is working!")
        print(f"     IP: {data.get('ip', '?')}")
        print(f"     Country: {data.get('geo', {}).get('country_code', '?')}")
        print(f"     City: {data.get('geo', {}).get('city', '?')}")
        return 0
    except requests.exceptions.ProxyError as e:
        print(f"[FAIL] Proxy error: {e}")
        return 1
    except requests.exceptions.Timeout:
        print("[FAIL] Timeout - proxy may be slow or unreachable")
        return 1
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Request error: {e}")
        if hasattr(e, "response") and e.response is not None:
            resp = e.response
            print(f"     Status: {resp.status_code}")
            print(f"     Body: {resp.text[:300]}")
            if "ip_forbidden" in resp.text.lower():
                print("\n     Hint: ip_forbidden often means:")
                print("     - Zone has IP whitelist; add your IP in BrightData dashboard")
                print("     - Zone is for different product (need Datacenter proxy zone)")
                print("     - Credentials/zone expired or invalid")
        return 1
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
