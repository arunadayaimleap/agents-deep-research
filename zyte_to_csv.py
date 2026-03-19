#!/usr/bin/env python3
"""
Convert Zyte results JSON to CSV.
Extracts: url, success, product_name, price, regular_price, currency, availability, brand, sku.
"""
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def safe_str(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    # Escape quotes for CSV
    if '"' in s or "," in s or "\n" in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def main():
    if len(sys.argv) < 2:
        inp = PROJECT_ROOT / "zyte_results_20260319_140544.json"
        out = inp.with_suffix(".csv")
        print(f"Usage: python zyte_to_csv.py <zyte_results.json> [output.csv]")
        print(f"Using: {inp} -> {out}")
    else:
        inp = Path(sys.argv[1])
        out = Path(sys.argv[2]) if len(sys.argv) > 2 else inp.with_suffix(".csv")

    if not inp.exists():
        print(f"[ERROR] {inp} not found")
        return 1

    data = json.loads(inp.read_text(encoding="utf-8"))
    results = data.get("results") or []

    cols = ["url", "success", "product_name", "price", "regular_price", "currency", "availability", "brand", "sku"]

    rows = []
    for r in results:
        url = ""
        if r.get("echoData"):
            url = r["echoData"].get("url") or r["echoData"].get("response", {}).get("url", "")
        elif r.get("response"):
            url = r["response"].get("url", "")

        success = r.get("success", False)
        prod = r.get("response", {}).get("product") or {} if success else {}
        if isinstance(prod, dict):
            name = prod.get("name") or ""
            price = prod.get("price") or prod.get("regularPrice") or ""
            reg_price = prod.get("regularPrice") or "" if price != prod.get("regularPrice") else ""
            currency = prod.get("currency") or prod.get("currencyRaw") or ""
            avail = prod.get("availability") or ""
            brand = ""
            b = prod.get("brand")
            if isinstance(b, dict):
                brand = b.get("name") or ""
            elif isinstance(b, str):
                brand = b
            sku = prod.get("sku") or ""
        else:
            name = price = reg_price = currency = avail = brand = sku = ""

        rows.append([url, success, name, price, reg_price, currency, avail, brand, sku])

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)

    print(f"[OK] Wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
