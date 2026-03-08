import asyncio
from deep_researcher.tools.browser_tools import raw_open_page, raw_get_page_text, raw_get_page_links, PlaywrightManager

async def test_crawler():
    # Use reliable test URLs - example.com and httpbin.org are known to work
    print("\n--- Testing example.com ---")
    res1 = await raw_open_page("https://example.com")
    print("Open result:", res1)
    
    print("\n--- Testing httpbin.org/html ---")
    res2 = await raw_open_page("https://httpbin.org/html")
    print("Open result:", res2)
    
    print("\n--- Testing Read ---")
    text = await raw_get_page_text()
    print("Text snippet:", text[:200], "...\nLength:", len(text))
    
    print("\n--- Testing Links (on example.com) ---")
    await raw_open_page("https://example.com")  # example.com has links
    links = await raw_get_page_links()
    print("Found", len(links), "links.")
    for i in range(min(5, len(links))):
        print(" ->", links[i])
        
    print("\nClosing...")
    await PlaywrightManager.close()
    print("Closed.")

if __name__ == "__main__":
    asyncio.run(test_crawler())
