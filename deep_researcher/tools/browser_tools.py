import asyncio
import os
import re
import json
from typing import List, Dict, Optional, Union
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from agents import function_tool

# Kameleo imports
try:
    from kameleo.local_api_client import KameleoLocalApiClient
    from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference
    KAMELEO_AVAILABLE = True
except ImportError:
    KAMELEO_AVAILABLE = False

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

async def _check_kameleo_available() -> bool:
    """Check if Kameleo Local API is running and accessible."""
    try:
        from kameleo.local_api_client import KameleoLocalApiClient
        client = KameleoLocalApiClient(endpoint='http://localhost:5050')
        fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
        return fps is not None and len(fps) > 0
    except Exception:
        return False


async def raw_get_product_price(url: str) -> str:
    """Fetch e-commerce product page via Kameleo + Playwright and extract pricing information with context."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Try Kameleo first if available
    if KAMELEO_AVAILABLE:
        kameleo_ok = await _check_kameleo_available()
        if kameleo_ok:
            return await _get_price_via_kameleo(url)
        else:
            return f"Kameleo is installed but Local API is not running. Ensure Kameleo service is started (run 'kameleo start' in terminal) and listening on http://localhost:5050"
    else:
        return await _get_price_via_playwright(url)


async def _get_price_via_kameleo(url: str) -> str:
    """Fetch product page via Kameleo (anti-bot bypass) and extract prices with context."""
    try:
        from kameleo.local_api_client import KameleoLocalApiClient
        from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference
        
        client = KameleoLocalApiClient(endpoint='http://localhost:5050')
        
        # Search for fingerprints
        fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
        if not fps:
            return "Error: No Kameleo fingerprints available. Ensure Kameleo Local API is running on http://localhost:5050"
        
        # Create profile
        profile = client.profile.create_profile(CreateProfileRequest(
            fingerprint_id=fps[0].id,
            name=f'price-extraction'
        ))
        
        try:
            # Start profile
            client.profile.start_profile(profile.id, BrowserSettings(
                arguments=['mute-audio'],
                preferences=[
                    Preference(key='profile.default_content_settings.images', value=1),
                ]
            ))
            
            # Connect Playwright using async API
            browser_ws = f'ws://localhost:5050/playwright/{profile.id}'
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(endpoint_url=browser_ws)
                contexts = browser.contexts
                if not contexts:
                    context = await browser.new_context()
                else:
                    context = contexts[0]
                page = await context.new_page()
                
                try:
                    # Navigate with shorter timeout - use domcontentloaded instead of networkidle
                    # This prevents infinite waits on pages with continuous reloads/updates
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                    status = response.status if response else "Unknown"
                    
                    if status != 200:
                        return f"Failed to load page: HTTP {status}"
                    
                    # Wait for initial content, but not too long
                    await page.wait_for_timeout(3000)
                    
                    # Check if page is still loading (has meta refresh or ongoing navigation)
                    # Try to extract content, if it's a redirect/error page, wait a bit more
                    html = await page.content()
                    
                    # Quick validation - if page is very small, might still be loading or error
                    if len(html) < 5000:
                        await page.wait_for_timeout(2000)
                        html = await page.content()
                    
                    title = await page.title()
                    
                    # Parse with BeautifulSoup to extract structured data
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract product title (try multiple common selectors)
                    product_title = title
                    title_selectors = [
                        'h1', 
                        '[data-testid="product-title"]',
                        '.product-title',
                        '.ProductTitle__productTitle',
                        '[itemprop="name"]'
                    ]
                    for selector in title_selectors:
                        elem = soup.select_one(selector)
                        if elem:
                            product_title = elem.get_text(strip=True)
                            break
                    
                    # Extract specifications (look for common spec patterns)
                    specs = []
                    spec_containers = soup.find_all(['dl', 'table', 'div'], {'class': re.compile(r'spec|attribute|detail', re.I)})
                    for container in spec_containers[:5]:  # Limit to 5
                        text = container.get_text(strip=True)
                        if text and len(text) > 10:
                            specs.append(text[:200])  # Limit each spec to 200 chars
                    
                    # Extract prices with context (50 chars before/after price)
                    price_pattern = r'.{0,50}(\$[\d,]+\.?\d*).{0,50}'
                    matches = re.finditer(price_pattern, html, re.DOTALL)
                    
                    prices_with_context = []
                    for match in matches:
                        price = match.group(1)
                        context = match.group(0).replace('\n', ' ').replace('\t', ' ')
                        context = ' '.join(context.split())
                        prices_with_context.append({'price': price, 'context': context})
                    
                    # Remove duplicates
                    seen = set()
                    unique_prices = []
                    for pc in prices_with_context:
                        key = (pc['price'], pc['context'])
                        if key not in seen:
                            seen.add(key)
                            unique_prices.append(pc)
                    
                    if not unique_prices:
                        return f"Title: {product_title}\nSpecs: {' | '.join(specs[:3]) if specs else 'Not found'}\nPrice: No prices found on page"
                    
                    # Sort by price amount
                    def price_to_float(p):
                        try:
                            return float(p['price'].replace('$', '').replace(',', ''))
                        except:
                            return 0
                    
                    unique_prices.sort(key=price_to_float, reverse=True)
                    
                    # Find likely product price (> $50 for e-commerce)
                    product_prices = [p for p in unique_prices if price_to_float(p) > 50]
                    
                    # Build comprehensive output
                    output_lines = [
                        f"Title: {product_title}",
                        f"URL: {url}",
                    ]
                    
                    if specs:
                        output_lines.append(f"Specs: {' | '.join(specs[:3])}")
                    
                    if product_prices:
                        main = product_prices[0]
                        output_lines.append(f"\nCurrent Price: {main['price']}")
                        output_lines.append(f"Context: {main['context'][:300]}")
                        
                        # Include additional info for LLM analysis
                        if 'Was' in main['context'] or 'was' in main['context'] or 'Save' in main['context']:
                            output_lines.append("[Note: Context indicates this may be a sale/discounted price]")
                        
                        # Include alternate prices for comparison
                        if len(product_prices) > 1:
                            output_lines.append(f"\nAlternate Price: {product_prices[1]['price']}")
                            output_lines.append(f"Context: {product_prices[1]['context'][:200]}")
                    else:
                        if unique_prices:
                            output_lines.append(f"\nTop Price Found: {unique_prices[0]['price']}")
                            output_lines.append(f"Context: {unique_prices[0]['context'][:300]}")
                            output_lines.append("[Note: Price may not be the main product price]")
                    
                    return "\n".join(output_lines)
                
                finally:
                    await page.close()
                    await browser.close()
        
        finally:
            # Stop profile
            try:
                client.profile.stop_profile(profile.id)
            except Exception:
                pass
    
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return f"Kameleo error: {str(e)}\n\nTroubleshooting:\n1. Ensure Kameleo Local API is running on http://localhost:5050\n2. Check: kameleo status or start the Kameleo service\n3. If page keeps reloading, check if it has meta refresh tags or JS redirects\n\nDetails:\n{tb[:500]}"


async def _get_price_via_playwright(url: str) -> str:
    """Fallback: Fetch page via plain Playwright (may be blocked by anti-bot)."""
    try:
        page = await PlaywrightManager.get_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=120000)

        if response and response.status == 200:
            await page.wait_for_timeout(3000)
            content = await page.content()
            title = await page.title()

            # Parse with BeautifulSoup to extract structured data
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract product title (try multiple common selectors)
            product_title = title
            title_selectors = [
                'h1', 
                '[data-testid="product-title"]',
                '.product-title',
                '.ProductTitle__productTitle',
                '[itemprop="name"]'
            ]
            for selector in title_selectors:
                elem = soup.select_one(selector)
                if elem:
                    product_title = elem.get_text(strip=True)
                    break
            
            # Extract specifications
            specs = []
            spec_containers = soup.find_all(['dl', 'table', 'div'], {'class': re.compile(r'spec|attribute|detail', re.I)})
            for container in spec_containers[:5]:
                text = container.get_text(strip=True)
                if text and len(text) > 10:
                    specs.append(text[:200])
            
            # Extract prices
            price_patterns = [
                r'\$[\d,]+\.?\d*',
                r'₹[\d,]+\.?\d*',
                r'£[\d,]+\.?\d*',
                r'€[\d,]+\.?\d*',
                r'AUD\s*\$[\d,]+\.?\d*',
                r'CAD\s*\$[\d,]+\.?\d*',
            ]

            found_prices = []
            for pattern in price_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                found_prices.extend(matches)

            # Build output
            output_lines = [
                f"Title: {product_title}",
                f"URL: {url}",
            ]
            
            if specs:
                output_lines.append(f"Specs: {' | '.join(specs[:3])}")
            
            if found_prices:
                output_lines.append(f"\nPrices Found: {', '.join(set(found_prices[:5]))}")
            else:
                output_lines.append("\nNo prices found on the product page.")
            
            return "\n".join(output_lines)
        else:
            status = response.status if response else "Unknown"
            return f"Page returned status {status}. Unable to access product information.\n\nNote: If this is an anti-bot protected site (Amazon, Walmart, Home Depot), install and start Kameleo:\n1. Download from https://www.kameleo.io/\n2. Start with: kameleo start\n3. Re-run the price comparison"

    except Exception as e:
        return f"Error fetching product price: {str(e)}"

@function_tool
async def get_product_price(url: str) -> str:
    """Fetches an e-commerce product page via Kameleo (with anti-bot bypass) and extracts comprehensive product information.
    
    Uses Kameleo Local API for anti-bot detection bypass. If Kameleo is not available, falls back to plain Playwright.
    Extracts product title, specifications, prices with surrounding context so LLM can determine original vs sale pricing.
    
    Use this to get the exact current price and product details from a specific product URL discovered through search.
    Works reliably on blocked e-commerce sites (Amazon, Walmart, Home Depot, etc.).
    
    Args:
        url: The full product URL (e.g., https://www.homedepot.com/p/...)
        
    Returns:
        Structured output including:
        - Title: Product name/title
        - URL: The fetched URL
        - Specs: Key product specifications
        - Current Price: Main selling price with context
        - Alternate Price (if found): Other price listings with context
        
        All prices include surrounding HTML context for LLM analysis to determine if original or sale price.
    """
    return await raw_get_product_price(url)
