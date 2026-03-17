#!/usr/bin/env python3
"""
Connect to an EXISTING Chrome instance (that you manually open) via CDP.
Instructions:
1. Open Chrome manually with: chrome.exe --remote-debugging-port=9222
2. Run this script
"""
import asyncio
import re
from playwright.async_api import async_playwright

URL = "https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606"

async def extract_price():
    print("=== Connecting to Chrome via CDP ===\n")
    print("Make sure Chrome is open with: chrome.exe --remote-debugging-port=9222\n")
    print(f"Target URL: {URL}\n")
    
    async with async_playwright() as p:
        try:
            # Connect to existing Chrome
            print("[*] Connecting to Chrome on localhost:9222...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            print("[OK] Connected!\n")
            
            # Create new context and page
            context = await browser.new_context()
            page = await context.new_page()
            
            # Navigate
            print("[*] Navigating to Home Depot...")
            response = await page.goto(URL, wait_until="networkidle", timeout=60000)
            
            status = response.status if response else "Unknown"
            title = await page.title()
            
            print(f"[OK] Loaded - Status: {status}, Title: {title}\n")
            
            # Wait for rendering
            print("[*] Waiting for page to fully render...")
            await page.wait_for_timeout(3000)
            
            # Extract HTML
            html = await page.content()
            print(f"[OK] Got {len(html)} chars of content\n")
            
            # Find prices
            print("[*] Searching for prices...")
            prices = re.findall(r'\$[\d,]+\.?\d*', html)
            
            if prices:
                unique = list(set(prices))
                print(f"[SUCCESS] Found {len(unique)} unique prices: {unique}\n")
                print(f"MAIN PRICE: {prices[0]}")
                return prices[0]
            else:
                print("[FAIL] No prices found")
                return None
                
        except Exception as e:
            print(f"[ERROR] {str(e)}")
            return None

if __name__ == "__main__":
    asyncio.run(extract_price())
