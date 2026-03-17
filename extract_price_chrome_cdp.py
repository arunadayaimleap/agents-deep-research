#!/usr/bin/env python3
"""
Connect to existing Chrome instance via CDP and extract price from Home Depot.
This avoids bot detection by using a real Chrome instance.
"""
import asyncio
import re
import subprocess
import time
from playwright.async_api import async_playwright

URL = "https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606"

async def extract_price_via_cdp():
    print("=== Connecting to Chrome via CDP ===\n")
    print(f"URL: {URL}\n")
    
    # Launch Chrome with remote debugging port
    print("[*] Launching Chrome with remote debugging...")
    chrome_process = subprocess.Popen([
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check"
    ])
    
    # Wait for Chrome to start
    await asyncio.sleep(3)
    
    try:
        # Connect to the running Chrome instance
        print("[*] Connecting to Chrome instance...")
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            print("[OK] Connected to Chrome\n")
            
            try:
                # Create new page/tab
                print("[*] Opening new tab...")
                context = await browser.new_context()
                page = await context.new_page()
                
                # Navigate to URL
                print("[*] Navigating to URL...")
                response = await page.goto(URL, wait_until="networkidle", timeout=60000)
                
                status = response.status if response else "Unknown"
                title = await page.title()
                current_url = page.url
                
                print(f"[OK] Page loaded")
                print(f"    Status: {status}")
                print(f"    Title: {title}")
                print(f"    URL: {current_url}\n")
                
                # Wait for content to render
                print("[*] Waiting for content to render (5 seconds)...")
                await page.wait_for_timeout(5000)
                
                # Get page content
                print("[*] Extracting content...")
                html = await page.content()
                print(f"    Content length: {len(html)} chars\n")
                
                # Extract price
                print("[*] Searching for price...")
                prices = re.findall(r'\$[\d,]+\.?\d*', html)
                
                if prices:
                    unique_prices = list(set(prices))
                    print(f"[SUCCESS] Found prices: {unique_prices}")
                    main_price = prices[0]
                    print(f"[RESULT] Main price: {main_price}\n")
                    return main_price
                else:
                    print("[FAIL] No price found\n")
                    return None
            finally:
                await browser.close()
                
    except Exception as e:
        print(f"[ERROR] {str(e)}\n")
        return None
    
    finally:
        # Terminate Chrome
        print("[*] Closing Chrome...")
        chrome_process.terminate()
        chrome_process.wait()

if __name__ == "__main__":
    price = asyncio.run(extract_price_via_cdp())
    print("\n" + "="*50)
    if price:
        print(f"EXTRACTED PRICE: {price}")
    else:
        print("NO PRICE EXTRACTED")
    print("="*50)
