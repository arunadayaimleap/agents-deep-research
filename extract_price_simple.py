#!/usr/bin/env python3
"""
Launch Chrome using Playwright directly with args, then extract price.
"""
import asyncio
import re
from playwright.async_api import async_playwright

URL = "https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606"

async def extract_price():
    print("=== Extracting Price via Playwright Chrome ===\n")
    print(f"URL: {URL}\n")
    
    async with async_playwright() as p:
        print("[*] Launching Chrome...")
        
        # Launch with custom args but NOT in headless mode (so we see the window)
        browser = await p.chromium.launch(
            headless=False,  # Headed mode - shows the browser window
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-setuid-sandbox",
                "--no-sandbox"
            ]
        )
        
        print("[OK] Browser launched\n")
        
        # Create a new page
        page = await browser.new_page()
        
        # Disable resource blocking  - CRITICAL
        print("[*] Navigating to URL...")
        response = await page.goto(URL, wait_until="networkidle", timeout=90000)
        
        status = response.status if response else "Unknown"
        title = await page.title()
        
        print(f"[OK] Page loaded")
        print(f"    Status: {status}")
        print(f"    Title: {title}")
        print(f"    URL: {page.url}\n")
        
        # Let it render
        print("[*] Waiting for full render (10 seconds)...")
        await page.wait_for_timeout(10000)
        
        # Extract HTML
        print("[*] Extracting page...")
        html = await page.content()
        print(f"[OK] Got {len(html)} chars\n")
        
        # Find prices
        print("[*] Searching for prices...")
        prices = re.findall(r'\$[\d,]+\.?\d*', html)
        
        if prices:
            unique = list(set(prices))
            print(f"[SUCCESS] Found {len(unique)} unique prices:")
            for p in unique[:15]:
                print(f"  - {p}")
            
            main_price = prices[0]
            print(f"\n[RESULT] Main price: {main_price}\n")
            
            await browser.close()
            return main_price
        else:
            print("[FAIL] No prices found")
            print(f"\nPage length: {len(html)} chars")
            if len(html) < 3000:
                print("Content preview:")
                print(html[:800])
            await browser.close()
            return None

if __name__ == "__main__":
    price = asyncio.run(extract_price())
    print("\n" + "="*50)
    if price:
        print(f"EXTRACTED PRICE: {price}")
    else:
        print("NO PRICE EXTRACTED")
    print("="*50)
