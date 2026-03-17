#!/usr/bin/env python3
"""
Launch Chrome with CDP and extract price from Home Depot.
Uses a new window via Chrome's remote debugging protocol.
"""
import asyncio
import re
import subprocess
import time
from playwright.async_api import async_playwright

URL = "https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606"

async def extract_price_via_new_window():
    print("=== Extracting Price via Chrome CDP (New Window) ===\n")
    print(f"URL: {URL}\n")
    
    # First, kill any existing Chrome processes with debugging port
    print("[*] Cleaning up old Chrome processes...")
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], 
                   capture_output=True)
    await asyncio.sleep(2)
    
    # Launch Chrome with remote debugging on new port
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    print("[*] Launching Chrome with CDP...")
    chrome_proc = subprocess.Popen([
        chrome_path,
        "--remote-debugging-port=9333",
        "--new-window",
        URL  # Open the URL directly in new window
    ])
    
    # Give Chrome time to start and initialize CDP
    print("[*] Waiting for Chrome to start and initialize CDP (10 seconds)...")
    for i in range(10):
        await asyncio.sleep(1)
        print(f"    {i+1}/10...", end="\r")
    print("\n")
    
    try:
        async with async_playwright() as p:
            print("[*] Connecting via CDP to localhost:9333...")
            
            # Retry connection
            browser = None
            for attempt in range(5):
                try:
                    browser = await p.chromium.connect_over_cdp("http://localhost:9333")
                    print(f"[OK] Connected to Chrome on attempt {attempt+1}\n")
                    break
                except Exception as e:
                    if attempt < 4:
                        print(f"[RETRY] Connection failed, retrying in 3 seconds...")
                        await asyncio.sleep(3)
                    else:
                        raise
            
            if not browser:
                raise Exception("Could not connect to Chrome after 5 attempts")
            
            # Get existing context/page
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
                pages = context.pages
                if pages:
                    page = pages[0]
                    print("[OK] Got existing page\n")
                else:
                    print("[WARN] No pages in context, creating one...")
                    page = await context.new_page()
                    await page.goto(URL, wait_until="networkidle", timeout=60000)
            else:
                print("[WARN] No contexts, creating one...")
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(URL, wait_until="networkidle", timeout=60000)
            
            # Get page info
            title = await page.title()
            current_url = page.url
            print(f"Title: {title}")
            print(f"URL: {current_url}\n")
            
            # Wait for content
            print("[*] Waiting for page to fully render (8 seconds)...")
            await page.wait_for_timeout(8000)
            
            # Extract content
            print("[*] Extracting page content...")
            html = await page.content()
            print(f"[OK] Got {len(html)} chars\n")
            
            # Search for prices
            print("[*] Searching for prices...")
            prices = re.findall(r'\$[\d,]+\.?\d*', html)
            
            if prices:
                unique = list(set(prices))
                print(f"[SUCCESS] Found {len(unique)} unique prices:")
                for p in unique[:10]:
                    print(f"  - {p}")
                
                main_price = prices[0]
                print(f"\n[RESULT] Main price: {main_price}\n")
                return main_price
            else:
                print("[FAIL] No prices found")
                
                # Debug: check if it's error page
                if len(html) < 5000:
                    print(f"\n[DEBUG] Small content ({len(html)} chars) - might be error page")
                    print("First 1000 chars:")
                    print(html[:1000])
                
                return None
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        print("\n[*] Closing Chrome...")
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=5)
        except:
            chrome_proc.kill()

if __name__ == "__main__":
    price = asyncio.run(extract_price_via_new_window())
    print("\n" + "="*50)
    if price:
        print(f"EXTRACTED PRICE: {price}")
    else:
        print("NO PRICE EXTRACTED")
    print("="*50)
