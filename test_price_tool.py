#!/usr/bin/env python3
"""Test the new get_product_price tool with BrightData proxy."""
import asyncio
from deep_researcher.tools.browser_tools import raw_get_product_price, PlaywrightManager

async def test_price_extraction():
    urls = [
        "https://www.homedepot.com/p/Frigidaire-36-in-26-cu-ft-Standard-Depth-Side-by-Side-Refrigerator-in-Stainless-Steel-FRSS2623AS/320970662",
        "https://www.amazon.com/dp/B0C8S6GR8Y",  # Some Amazon product
    ]

    for url in urls:
        print(f"\n🔍 Testing: {url}")
        try:
            result = await raw_get_product_price(url)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")

    await PlaywrightManager.close()

if __name__ == "__main__":
    asyncio.run(test_price_extraction())
