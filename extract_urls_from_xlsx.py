#!/usr/bin/env python3
"""
Extract all URLs from urls-mixed.xlsx, including hyperlink targets.
Saves to urls_extracted.json.
"""
import json
import re
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Install openpyxl: pip install openpyxl")
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parent
XLSX_PATH = PROJECT_ROOT / "urls-mixed.xlsx"
OUTPUT_PATH = PROJECT_ROOT / "urls_extracted.json"


def is_url_like(s: str) -> bool:
    """Check if string looks like a URL."""
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return True
    # Bare domain
    if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9.-]*\.(com|org|net|io|co|ae|au)[^\s]*", s):
        return True
    return False


def normalize_url(s: str) -> str:
    """Ensure URL has scheme."""
    s = s.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9.-]*\.(com|org|net|io|co|ae)[/\w\-\.\?\=\&\%\#\-]*", s):
        return "https://" + s
    return s


def extract_urls(path: Path) -> list[dict]:
    """Extract URLs from Excel, including hyperlink targets."""
    wb = openpyxl.load_workbook(path, read_only=False, data_only=False)
    ws = wb.active

    results = []
    seen = set()

    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_col=1), start=1):
        cell = row[0]
        url = None
        display_text = None

        # Try hyperlink target first (actual URL)
        if cell.hyperlink:
            try:
                # target = link destination, display = optional display text
                url = getattr(cell.hyperlink, "target", None) or getattr(
                    cell.hyperlink, "display", None
                )
                display_text = str(cell.value).strip() if cell.value else None
            except Exception:
                pass

        # Fallback: cell value if it looks like a URL
        if not url and cell.value:
            val = str(cell.value).strip()
            if is_url_like(val):
                url = val
                display_text = None

        if url:
            url = normalize_url(url)
            if url not in seen and is_url_like(url):
                seen.add(url)
                results.append({
                    "row": row_idx,
                    "url": url,
                    "display_text": display_text[:80] + "..." if display_text and len(display_text) > 80 else display_text,
                })

    wb.close()
    return results


def main():
    if not XLSX_PATH.exists():
        print(f"[ERROR] {XLSX_PATH} not found")
        return 1

    urls = extract_urls(XLSX_PATH)
    urls_only = [r["url"] for r in urls]

    output = {
        "source": str(XLSX_PATH.name),
        "total_count": len(urls),
        "urls": urls_only,
        "details": urls,
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"[OK] Extracted {len(urls)} URLs to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
