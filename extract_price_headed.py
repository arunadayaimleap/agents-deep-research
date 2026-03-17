#!/usr/bin/env python3
"""
Direct price extraction using Playwright in headed mode with BrightData proxy.
"""
import asyncio
import re
from playwright.async_api import async_playwright

BRIGHTDATA_PROXY = "http://brd-customer-hl_baa2623c-zone-static:tnej9bv3rk96@brd.superproxy.io:33335"
URL = "https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606"

async def extract_price_headed():
    async with async_playwright() as p:
        print("=== Opening Home Depot in Headed Browser ===\n")
        print(f"URL: {URL}\n")
        
        # Launch in HEADED mode (visible browser) - NO PROXY
        browser = await p.chromium.launch(
            headless=False,  # HEADED MODE - you'll see the browser window
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True,
        )
        
        page = await context.new_page()
        
        # DO NOT block anything - let JavaScript and CSS load properly
        # (Removed resource blocking to allow full page rendering)
        
        try:
            print("[*] Navigating to page...")
            response = await page.goto(URL, wait_until="networkidle", timeout=120000)
            
            status = response.status if response else "Unknown"
            title = await page.title()
            current_url = page.url
            
            print(f"[OK] Page loaded")
            print(f"    Status: {status}")
            print(f"    Title: {title}")
            print(f"    URL: {current_url}\n")
            
            # Wait for page to fully render
            print("[*] Waiting for page content to render (10 seconds)...")
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
                print("[OK] Page fully loaded")
            except:
                print("[WARN] Load timeout, continuing...")
            
            # Get page content
            print("[*] Extracting content...")
            html = await page.content()
            print(f"    Content length: {len(html)} chars\n")
            
            # Extract price
            print("[*] Searching for price...")
            prices = re.findall(r'\$[\d,]+\.?\d*', html)
            
            if prices:
                print(f"[SUCCESS] Found prices: {list(set(prices))}")
                main_price = prices[0]
                print(f"[RESULT] Main price: {main_price}\n")
                
                # Try to find it near "price" text
                price_context = re.search(r'(price|Price|PRICE)[^\$]*(\$[\d,]+\.?\d*)', html, re.IGNORECASE)
                if price_context:
                    print(f"[DETAIL] Price context: ...{price_context.group(0)[:100]}...\n")
                
                return main_price
            else:
                print("[FAIL] No price found\n")
                return None
                
        except Exception as e:
            print(f"[ERROR] {str(e)}\n")
            return None
        
        finally:
            # Keep browser open for 3 seconds
            print("[*] Browser will close in 3 seconds...")
            try:
                await page.wait_for_timeout(3000)
            except:
                pass
            await browser.close()

if __name__ == "__main__":
    price = asyncio.run(extract_price_headed())
    print("\n" + "="*50)
    if price:
        print(f"EXTRACTED PRICE: {price}")
    else:
        print("NO PRICE EXTRACTED")
    print("="*50)
