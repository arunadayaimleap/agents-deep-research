import asyncio
import re
from typing import List, Dict, Optional, Union
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from agents import function_tool

# --- Singleton Browser Manager ---
class PlaywrightManager:
    _instance = None
    _playwright = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _page: Optional[Page] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_page(cls) -> Page:
        async with cls._lock:
            if cls._page is None:
                if cls._playwright is None:
                    cls._playwright = await async_playwright().start()
                if cls._browser is None:
                    # Launching with BrightData proxy for e-commerce access
                    brightdata_proxy = os.getenv("BRIGHTDATA_PROXY", "http://brd-customer-hl_baa2623c-zone-static:tnej9bv3rk96@brd.superproxy.io:33335")
                    cls._browser = await cls._playwright.chromium.launch(
                        headless=True,
                        proxy={"server": brightdata_proxy},
                        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
                    )
                if cls._context is None:
                    cls._context = await cls._browser.new_context(
                        viewport={'width': 1280, 'height': 800},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        ignore_https_errors=True,
                    )
                    # Block images/media/fonts to save bandwidth; allow stylesheets (some sites need them to render)
                    await cls._context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

                cls._page = await cls._context.new_page()
            return cls._page

    @classmethod
    async def close(cls):
        """Cleanup resources."""
        async with cls._lock:
            if cls._page:
                await cls._page.close()
                cls._page = None
            if cls._context:
                await cls._context.close()
                cls._context = None
            if cls._browser:
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None


# --- Tool Definitions ---

async def raw_open_page(url: str) -> str:
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    try:
        page = await PlaywrightManager.get_page()
        # waitUntil="domcontentloaded" is faster, wait max 60s for slow networks
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait a small bit extra for any immediate JS redirects or dynamic renders
        await page.wait_for_timeout(2000)
        
        current_url = page.url
        title = await page.title()
        status = response.status if response else "Unknown"
        return f"Successfully opened {current_url}. Page title: '{title}'. HTTP Status: {status}"
    except Exception as e:
        # Reset to blank page so subsequent get_page_text/links don't read error page
        try:
            page = await PlaywrightManager.get_page()
            await page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            pass
        return f"Error opening page {url}: {str(e)}"

@function_tool
async def open_page(url: str) -> str:
    """Navigates the browser to the specified URL. Wait for page load before reading.
    
    Args:
        url: The absolute URL to visit (must start with http:// or https://)
        
    Returns:
        Status message about the page load.
    """
    return await raw_open_page(url)

async def raw_get_page_text() -> str:
    try:
        page = await PlaywrightManager.get_page()
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove hidden tags and scripts
        for element in soup(["script", "style", "noscript", "meta", "nav", "footer", "iframe"]):
            element.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        # Clean up excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Cap length to avoid massive context explosion, but keep it generous
        max_len = 12000
        if len(text) > max_len:
            text = text[:max_len] + "\n...[Content Truncated]..."
            
        return text if text else "Page appears to have no visible text."
    except Exception as e:
        return f"Error extracting page text: {str(e)}"

@function_tool
async def get_page_text() -> str:
    """Extracts all visible text from the currently open webpage.
    Often used immediately after open_page() to read the content.
    
    Returns:
        The extracted visible text, cleaned of script/style tags.
    """
    return await raw_get_page_text()

async def raw_get_page_links() -> List[Dict[str, str]]:
    try:
        page = await PlaywrightManager.get_page()
        content = await page.content()
        base_url = page.url
        soup = BeautifulSoup(content, 'html.parser')
        
        links = []
        seen_urls = set()
        
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            
            # Skip empty links, javascript, or anchors
            if not text or not href or href.startswith(('javascript:', '#', 'mailto:', 'tel:')):
                continue
                
            # Make absolute URL
            abs_url = urljoin(base_url, href)
            
            # De-duplicate
            if abs_url in seen_urls:
                continue
                
            seen_urls.add(abs_url)
            links.append({"text": text, "url": abs_url})
            
            if len(links) >= 50:
                break
                
        return links
    except Exception as e:
        return [{"error": f"Failed to extract links: {str(e)}"}]

@function_tool
async def get_page_links() -> List[Dict[str, str]]:
    """Extracts a list of useful navigation links from the current page.
    Use this to find links to "Contact Us", "About", or employee directories.
    
    Returns:
        A list of dictionaries, each containing 'text' (the link text) and 'url' (absolute URL). 
        Only returns up to 50 links to avoid overwhelming the context.
    """
    return await raw_get_page_links()

async def raw_click_element(selector_or_text: str) -> str:
    try:
        page = await PlaywrightManager.get_page()
        # Look for literal text match softly
        locators = [
            page.locator(f"text='{selector_or_text}'").first,
            page.get_by_text(selector_or_text, exact=False).first
        ]
        
        success = False
        for loc in locators:
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click(timeout=5000)
                # Wait for any network navigation after clicking
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                except:
                    # Ignore timeout, it might have been an AJAX click
                    pass
                success = True
                break
                
        if success:
            return f"Successfully clicked element containing '{selector_or_text}'. Current URL is now: {page.url}"
        else:
            return f"Could not find or click an element containing '{selector_or_text}'."
            
    except Exception as e:
        return f"Error clicking element: {str(e)}"

@function_tool
async def click_element(selector_or_text: str) -> str:
    """Attempts to click a button or link on the page that matches the given text.
    Use this to click through directories, accept cookies, or navigate to a contact page.
    
    Args:
        selector_or_text: Exact visible text of the button/link you want to click (e.g., "Contact Us" or "Next Page")
    
    Returns:
        Result of the click action.
    """
    return await raw_click_element(selector_or_text)

async def raw_go_back() -> str:
    try:
        page = await PlaywrightManager.get_page()
        await page.go_back(wait_until="domcontentloaded", timeout=15000)
        return f"Gone back successfully. Current URL is now: {page.url}"
    except Exception as e:
        return f"Error navigating back: {str(e)}"

@function_tool
async def go_back() -> str:
    """Clicks the browser back button to return to the previous page.

    Returns:
        Status message of the back navigation.
    """
    return await raw_go_back()

# --- Price Extraction Tool for E-commerce ---

async def raw_get_product_price(url: str) -> str:
    """Fetch e-commerce product page and extract pricing information."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        page = await PlaywrightManager.get_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        if response and response.status == 200:
            await page.wait_for_timeout(3000)  # Wait for dynamic content
            content = await page.content()

            # Extract price using common patterns
            import re
            price_patterns = [
                r'\$[\d,]+\.?\d*',  # $1,299.00 or $1299
                r'₹[\d,]+\.?\d*',  # ₹1,29,900 (Indian Rupee)
                r'£[\d,]+\.?\d*',  # £1,299.00 (British Pound)
                r'€[\d,]+\.?\d*',  # €1,299.00 (Euro)
                r'AUD\s*\$[\d,]+\.?\d*',  # AUD $1,299.00
                r'CAD\s*\$[\d,]+\.?\d*',  # CAD $1,299.00
            ]

            found_prices = []
            for pattern in price_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                found_prices.extend(matches)

            if found_prices:
                # Return the most common price (assuming it's the main product price)
                # In practice, you'd want more sophisticated logic to identify the exact product price
                main_price = found_prices[0] if found_prices else None
                return f"Found product price: {main_price}. All prices found: {', '.join(set(found_prices))}"
            else:
                return "No price found on the product page."
        else:
            status = response.status if response else "Unknown"
            title = await page.title()
            return f"Page returned status {status}, title: '{title}'. Unable to access product information."

    except Exception as e:
        return f"Error fetching product price: {str(e)}"

@function_tool
async def get_product_price(url: str) -> str:
    """Fetches an e-commerce product page via BrightData proxy and extracts pricing information.
    Use this to get the exact price of a specific product URL discovered through search.

    Args:
        url: The full product URL (e.g., from Amazon, Walmart, Home Depot, etc.)

    Returns:
        The extracted product price(s) or error message.
    """
    return await raw_get_product_price(url)
