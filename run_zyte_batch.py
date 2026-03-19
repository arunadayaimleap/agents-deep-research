#!/usr/bin/env python3
"""
Zyte API batch runner: parallel requests, save full responses to JSON.

Usage:
  python run_zyte_batch.py           # 10 URLs default
  python run_zyte_batch.py -n 100   # 100 URLs

Requires:
- ZYTE_API_KEY in .env
- urls-mixed.xlsx in project root
"""
import argparse
import json
import os
import re
import random
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
XLSX_PATH = PROJECT_ROOT / "urls-mixed.xlsx"


def load_dotenv():
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass


def load_urls_from_xlsx(path: Path, n: int, random_sample: bool = True) -> list[str]:
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


def to_json_serializable(obj):
    """Convert response to JSON-serializable form (handle special types)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_serializable(x) for x in obj]
    if hasattr(obj, "__dict__"):
        return str(obj)
    return str(obj)


def main():
    load_dotenv()
    api_key = os.getenv("ZYTE_API_KEY")
    if not api_key:
        print("[ERROR] ZYTE_API_KEY not found in .env")
        return 1

    parser = argparse.ArgumentParser(description="Zyte API batch - parallel fetch, save to JSON")
    parser.add_argument("-n", type=int, default=10, help="Number of URLs (default 10)")
    parser.add_argument("--n-conn", type=int, default=30, help="Concurrent connections (default 30)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output JSON path (default: zyte_results_<timestamp>.json)")
    args = parser.parse_args()

    if not XLSX_PATH.exists():
        print(f"[ERROR] {XLSX_PATH} not found")
        return 1

    urls = load_urls_from_xlsx(XLSX_PATH, n=args.n, random_sample=True)
    if not urls:
        print("[ERROR] No valid URLs in urls-mixed.xlsx")
        return 1

    output_path = Path(args.output) if args.output else PROJECT_ROOT / f"zyte_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print(f"[*] Zyte API batch")
    print(f"[*] URLs: {len(urls)} | n_conn: {args.n_conn}")
    print(f"[*] Output: {output_path}\n")

    from zyte_api import ZyteAPI, RequestError

    client = ZyteAPI(api_key=api_key, n_conn=args.n_conn)

    # Build queries with echoData to track URL/index (results come in completion order)
    queries = []
    for i, url in enumerate(urls):
        queries.append({
            "url": url,
            "product": True,
            "echoData": {"idx": i, "url": url},
        })

    results = []

    with client.session() as session:
        for result_or_exception in session.iter(queries):
            if isinstance(result_or_exception, dict):
                # Success - store full response
                results.append({
                    "success": True,
                    "echoData": result_or_exception.get("echoData"),
                    "response": result_or_exception,
                })
                echo = result_or_exception.get("echoData", {})
                idx = echo.get("idx", "?")
                prod = result_or_exception.get("product") or {}
                price = prod.get("price", prod.get("regularPrice", "-"))
                print(f"  [{idx+1}/{len(urls)}] OK - price: {price}")

            elif isinstance(result_or_exception, RequestError):
                # API error - store serializable info
                err_obj = {
                    "success": False,
                    "error_type": "RequestError",
                    "error": str(result_or_exception),
                    "status": getattr(result_or_exception, "status_code", None),
                    "echoData": getattr(result_or_exception, "echo_data", None),
                }
                results.append(err_obj)
                print(f"  [?/{len(urls)}] FAIL - {str(result_or_exception)[:80]}")

            else:
                # Other exception
                results.append({
                    "success": False,
                    "error_type": type(result_or_exception).__name__,
                    "error": str(result_or_exception),
                    "echoData": None,
                })
                print(f"  [?/{len(urls)}] FAIL - {str(result_or_exception)[:80]}")

    # Build final output with metadata
    output = {
        "metadata": {
            "total_urls": len(urls),
            "total_results": len(results),
            "success_count": sum(1 for r in results if r.get("success")),
            "fail_count": sum(1 for r in results if not r.get("success")),
            "urls": urls,
            "n_conn": args.n_conn,
            "timestamp": datetime.now().isoformat(),
        },
        "results": [to_json_serializable(r) for r in results],
    }

    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n[OK] Saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
