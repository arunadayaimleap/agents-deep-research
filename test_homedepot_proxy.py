#!/usr/bin/env python3
"""Test fetching Home Depot product price via Playwright with free USA proxy."""
import asyncio
import sys
from playwright.async_api import async_playwright

# BrightData static proxy
BRIGHTDATA_PROXY = "http://brd-customer-hl_baa2623c-zone-static:tnej9bv3rk96@brd.superproxy.io:33335"

async def test_brightdata_proxy():
    print(f"\n🔍 Testing BrightData proxy: {BRIGHTDATA_PROXY}")

    async with async_playwright() as p:
        try:
            # Launch with BrightData proxy
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": BRIGHTDATA_PROXY},
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
            )

            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )

            page = await context.new_page()
            await context.route("**/*", lambda route: route.abort()
                              if route.request.resource_type in ["image", "media", "font"]
                              else route.continue_())

            response = await page.goto(
                "https://www.homedepot.com/p/Frigidaire-36-in-26-cu-ft-Standard-Depth-Side-by-Side-Refrigerator-in-Stainless-Steel-FRSS2623AS/320970662",
                wait_until="domcontentloaded",
                timeout=15000
            )

            current_url = page.url
            title = await page.title()
            status = response.status if response else "Unknown"

            print(f"  Status: {status} | Title: '{title}' | URL: {current_url[:80]}...")

            if status == 200 and "Error" not in title and "Oops" not in title:
                print("  ✅ Success! Getting content...")
                text = await page.content()
                print(f"  Content length: {len(text)} chars")

                # Look for price
                import re
                price_match = re.search(r'\$[\d,]+\.?\d*', text)
                if price_match:
                    print(f"  💰 Found price: {price_match.group(0)}")
                    return True
                else:
                    print("  ❌ No price found in content")
            else:
                print("  ❌ Blocked or error")

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:80]}...")

        finally:
            await browser.close()

    return False

async def main():
    print("Testing Home Depot access with BrightData static proxy...")

    success = await test_brightdata_proxy()

    if success:
        print("\n✅ BrightData proxy successfully accessed Home Depot!")
        print("💡 This proxy can be used for e-commerce scraping")
    else:
        print("\n❌ BrightData proxy could not access Home Depot")
        print("💡 Check proxy credentials or zone configuration")

if __name__ == "__main__":
    asyncio.run(main())
