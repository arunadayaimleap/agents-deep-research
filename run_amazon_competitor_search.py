#!/usr/bin/env python3
"""
Get competitor URLs for Amazon products from first 5 URLs in a CSV/XLSX file.

Logic: All URLs are from Amazon (same domain). As soon as we get competitors from
the first URL that returns any, we stop and save — the competitor list would be
the same for any Amazon product.

Usage:
  python run_amazon_competitor_search.py                    # urls-amazon.xlsx
  python run_amazon_competitor_search.py -i urls.csv         # CSV file
  python run_amazon_competitor_search.py -i urls-amazon.xlsx -o competitors.json

Requires: SERPER_API_KEY in .env
"""
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent

ECOMMERCE_DOMAINS = {
    "amazon.com", "amazon.", "walmart.com", "ebay.com", "ebay.", "target.com",
    "bestbuy.com", "homedepot.com", "lowes.com", "costco.com", "etsy.com",
    "depop.com", "poshmark.com", "alibaba.com", "sephora.com", "sephora.com.au",
    "barnesandnoble.com", "chewy.com", "wayfair.com", "overstock.com",
    "newegg.com", "adorama.com", "harborfreight.com", "nordstrom.com",
    "macys.com", "kohls.com", "jcpenney.com", "flipkart.com", "croma.com",
}
EXCLUDE_DOMAIN = "amazon.com"


def load_dotenv():
    try:
        from dotenv import load_dotenv as _load
        _load(PROJECT_ROOT / ".env")
    except ImportError:
        pass


def url_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_competitor_url(url: str) -> bool:
    domain = url_domain(url)
    if domain == EXCLUDE_DOMAIN or "amazon" in domain:
        return False
    for eco in ECOMMERCE_DOMAINS:
        if eco in domain:
            return True
    return False


def extract_asin(amazon_url: str) -> str | None:
    """Extract ASIN from Amazon product URL (e.g. /dp/B0XXXX or /gp/product/B0XXXX)."""
    m = re.search(r"/dp/([A-Z0-9]{10})", amazon_url, re.I)
    if m:
        return m.group(1)
    m = re.search(r"/gp/product/([A-Z0-9]{10})", amazon_url, re.I)
    if m:
        return m.group(1)
    m = re.search(r"/product/([A-Z0-9]{10})", amazon_url, re.I)
    if m:
        return m.group(1)
    return None


def load_urls_csv(path: Path, limit: int = 5) -> list[dict]:
    """Load URLs from CSV. Expects url in col 0, optional title in col 1."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            if not row:
                continue
            url = (row[0] or "").strip()
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                continue
            title = (row[1] or "").strip() if len(row) > 1 else None
            rows.append({"url": url, "title": title})
    return rows


def load_urls_xlsx(path: Path, limit: int = 5) -> list[dict]:
    """Load URLs from Excel (first column, hyperlinks or values)."""
    try:
        import openpyxl
    except ImportError:
        print("[ERROR] Install openpyxl: pip install openpyxl")
        return []
    wb = openpyxl.load_workbook(path, read_only=False, data_only=False)
    ws = wb.active
    rows = []
    seen = set()
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_col=2), start=1):
        if len(rows) >= limit:
            break
        cell = row[0]
        url = None
        title = (row[1].value or "").strip() if len(row) > 1 and row[1].value else None
        if cell.hyperlink:
            url = getattr(cell.hyperlink, "target", None) or getattr(cell.hyperlink, "display", None)
            if not title and cell.value:
                title = str(cell.value).strip()
        if not url and cell.value:
            val = str(cell.value).strip()
            if val.startswith("http://") or val.startswith("https://"):
                url = val
        if url:
            url = str(url).strip()
            if url.startswith("http") and url not in seen:
                seen.add(url)
                rows.append({"url": url, "title": title})
    wb.close()
    return rows


def serper_search(query: str, api_key: str, num: int = 20) -> dict | None:
    import urllib.request
    payload = {"q": query, "num": num}
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-KEY": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [ERR] {str(e)[:100]}")
        return None


def get_competitors(serp_data: dict, max_results: int = 15) -> list[dict]:
    competitors = []
    organic = serp_data.get("organic") or []
    for entry in organic:
        if not isinstance(entry, dict):
            continue
        link = entry.get("link") or entry.get("url") or ""
        if not link or not is_competitor_url(link):
            continue
        rank = entry.get("position") or entry.get("rank") or len(competitors) + 1
        competitors.append({"url": link, "title": (entry.get("title") or "")[:200], "rank": rank})
        if len(competitors) >= max_results:
            break
    return competitors


def main():
    load_dotenv()
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("[ERROR] SERPER_API_KEY not found in .env")
        return 1

    import argparse
    parser = argparse.ArgumentParser(description="Amazon competitor URLs from first 5 in file")
    parser.add_argument("-i", "--input", type=str, default=None, help="Input CSV or XLSX (default: urls-amazon.xlsx)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--limit", type=int, default=5, help="Max URLs to try (default 5)")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between requests")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else PROJECT_ROOT / "urls-amazon.xlsx"
    if not input_path.exists():
        # Fallback to CSV with same stem
        csv_path = input_path.with_suffix(".csv")
        if csv_path.exists():
            input_path = csv_path
        else:
            print(f"[ERROR] {input_path} not found")
            return 1

    if input_path.suffix.lower() == ".csv":
        entries = load_urls_csv(input_path, limit=args.limit)
    else:
        entries = load_urls_xlsx(input_path, limit=args.limit)

    if not entries:
        print("[ERROR] No URLs found in file")
        return 1

    output_path = Path(args.output) if args.output else PROJECT_ROOT / f"amazon_competitors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print("[*] Amazon competitor search (stop on first success)")
    print(f"[*] Input: {input_path} | URLs to try: {len(entries)}")
    print(f"[*] Output: {output_path}\n")

    competitors = []
    winning_url = None
    winning_query = None

    for i, entry in enumerate(entries):
        url = entry["url"]
        title = entry.get("title") or ""
        asin = extract_asin(url)

        # Build search query: prefer title, else ASIN
        if title and len(title) > 5 and not title.startswith("http"):
            query = title
            if len(query) > 80:
                query = query[:77] + "..."
        elif asin:
            query = asin
        else:
            print(f"  [{i+1}] SKIP - no title or ASIN for {url[:60]}...")
            continue

        print(f"  [{i+1}] Searching: {query[:55]}...")

        serp = serper_search(query, api_key)
        if not serp:
            time.sleep(args.delay)
            continue

        organic = serp.get("organic") or []
        if not organic:
            # Retry without quotes for long queries
            if len(query) > 30:
                serp = serper_search(query, api_key)  # already without quotes
            time.sleep(args.delay)
            if not (serp and serp.get("organic")):
                print(f"       -> 0 results")
                continue

        competitors = get_competitors(serp)
        if competitors:
            winning_url = url
            winning_query = query
            print(f"       -> {len(competitors)} competitors (stopping)")
            break
        print(f"       -> 0 competitors")
        time.sleep(args.delay)

    output = {
        "metadata": {
            "source_file": str(input_path.name),
            "urls_tried": len(entries),
            "winning_url": winning_url,
            "search_query": winning_query,
            "provider": "serper",
            "timestamp": datetime.now().isoformat(),
        },
        "competitors": competitors,
    }

    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\n[OK] Saved {len(competitors)} competitor URLs to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
