#!/usr/bin/env python3
"""Test fetching Home Depot product price via Playwright browser tools."""
import asyncio
import re
from deep_researcher.tools.browser_tools import raw_open_page, raw_get_page_text, PlaywrightManager

URL = "https://www.homedepot.com/p/Frigidaire-36-in-26-cu-ft-Standard-Depth-Side-by-Side-Refrigerator-in-Stainless-Steel-FRSS2623AS/320970662"

def extract_price(text: str) -> str | None:
    """Look for common price patterns: $1,299.00 or $1299"""
    # Match $X,XXX.XX or $X.XX
    m = re.search(r'\$[\d,]+\.?\d*', text)
    return m.group(0) if m else None

async def main():
    print(f"Opening: {URL}\n")
    res = await raw_open_page(URL)
    print("Open result:", res)
    
    text = await raw_get_page_text()
    print(f"\nPage text length: {len(text)} chars")
    print("\n--- First 2000 chars ---")
    print(text[:2000])
    print("\n--- Price search ---")
    price = extract_price(text)
    print(f"Extracted price: {price}")
    
    # Also look for common price-related phrases
    if "verify" in text.lower() or "captcha" in text.lower() or "robot" in text.lower():
        print("\n⚠️ Page may have blocked/verification content")
    
    await PlaywrightManager.close()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(main())
