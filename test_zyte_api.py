#!/usr/bin/env python3
"""
Test Zyte API: fetch details for one random URL from urls-mixed.xlsx.

Usage: python test_zyte_api.py

Requires:
- ZYTE_API_KEY in .env
- urls-mixed.xlsx in project root
- pip install zyte-api python-dotenv
"""
import json
import os
import re
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
XLSX_PATH = PROJECT_ROOT / "urls-mixed.xlsx"


def load_dotenv():
    """Load .env if python-dotenv available."""
    try:
        from dotenv import load_dotenv
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass


def load_one_url_from_xlsx(path: Path) -> str | None:
    """Load one random URL from xlsx. Returns first column value if it's a valid URL."""
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
    return random.choice(urls) if urls else None


def main():
    load_dotenv()
    api_key = os.getenv("ZYTE_API_KEY")
    if not api_key:
        print("[ERROR] ZYTE_API_KEY not found in .env")
        return 1

    if not XLSX_PATH.exists():
        print(f"[ERROR] {XLSX_PATH} not found")
        return 1

    url = load_one_url_from_xlsx(XLSX_PATH)
    if not url:
        print("[ERROR] No valid URLs in urls-mixed.xlsx")
        return 1

    print(f"[*] Zyte API test")
    print(f"[*] URL: {url}\n")

    try:
        from zyte_api import ZyteAPI

        client = ZyteAPI(api_key=api_key)

        # Request: product extraction for e-commerce pages (can't combine with httpResponseBody)
        request = {
            "url": url,
            "product": True,
        }

        print("[*] Fetching via Zyte API...")
        response = client.get(request)

        print("\n" + "=" * 70)
        print("RESPONSE")
        print("=" * 70)

        # Product extraction (if available)
        if "product" in response and response["product"]:
            prod = response["product"]
            print("\n[PRODUCT EXTRACTED]")
            for k, v in prod.items():
                if v is not None and str(v).strip():
                    val_str = str(v)[:200] + "..." if len(str(v)) > 200 else str(v)
                    print(f"  {k}: {val_str}")
        else:
            print("\n[PRODUCT] (none - page may not be a product)")

        # HTTP response metadata
        if "statusCode" in response:
            print(f"\n[HTTP] statusCode: {response['statusCode']}")
        if "url" in response:
            print(f"[HTTP] final URL: {response['url'][:80]}...")

        # Body length if present
        if "httpResponseBody" in response:
            import base64
            body_b64 = response["httpResponseBody"]
            body = base64.b64decode(body_b64).decode("utf-8", errors="replace")
            print(f"[HTTP] body length: {len(body)} chars")
            print(f"\n[HTML PREVIEW] (first 500 chars):\n{body[:500]}...")

        print("\n" + "=" * 70)
        print("[OK] Zyte API request succeeded")
        return 0

    except ImportError:
        print("[ERROR] zyte-api not installed. Run: pip install zyte-api")
        return 1
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
