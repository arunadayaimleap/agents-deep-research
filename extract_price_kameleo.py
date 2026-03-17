#!/usr/bin/env python3
"""
Extract Home Depot price using Kameleo + Playwright.
Kameleo provides real, fingerprinted browsers that bypass anti-bot detection.
"""
import re
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest
from playwright.sync_api import sync_playwright

URL = "https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606"

def extract_price_with_kameleo():
    print("=== Extracting Price with Kameleo + Playwright ===\n")
    print(f"URL: {URL}\n")
    
    try:
        # Connect to Kameleo Local API
        print("[*] Connecting to Kameleo Local API...")
        client = KameleoLocalApiClient(endpoint='http://localhost:5050')
        print("[OK] Connected to Kameleo\n")
        
        # Search for desktop Chrome fingerprints
        print("[*] Searching for Chrome fingerprints...")
        fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
        if not fps:
            print("[ERROR] No fingerprints found")
            return None
        print(f"[OK] Found {len(fps)} fingerprints\n")
        
        # Create a profile with the first fingerprint
        print(f"[*] Creating Kameleo profile...")
        profile = client.profile.create_profile(CreateProfileRequest(
            fingerprint_id=fps[0].id,
            name='homedepot-price-extraction'
        ))
        print(f"[OK] Profile created: {profile.id}\n")
        
        try:
            # Connect Playwright to Kameleo profile
            print("[*] Connecting Playwright to Kameleo profile...")
            browser_ws = f'ws://localhost:5050/playwright/{profile.id}'
            
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(endpoint_url=browser_ws)
                print("[OK] Playwright connected\n")
                
                # Get first page/context
                context = browser.contexts[0]
                page = context.new_page()
                
                # Navigate
                print("[*] Navigating to Home Depot...")
                response = page.goto(URL, wait_until='networkidle', timeout=90000)
                
                status = response.status if response else "Unknown"
                title = page.title()
                
                print(f"[OK] Page loaded")
                print(f"    Status: {status}")
                print(f"    Title: {title}\n")
                
                # Wait for rendering
                print("[*] Waiting for page to fully render (8 seconds)...")
                page.wait_for_timeout(8000)
                
                # Extract HTML
                print("[*] Extracting page content...")
                html = page.content()
                print(f"[OK] Got {len(html)} chars\n")
                
                # Find prices with context
                print("[*] Extracting prices with context...")
                
                # Find all prices with surrounding context (50 chars before and after)
                price_pattern = r'.{0,50}(\$[\d,]+\.?\d*).{0,50}'
                matches = re.finditer(price_pattern, html)
                
                price_contexts = []
                for match in matches:
                    price = match.group(1)
                    context = match.group(0).replace('\n', ' ').strip()
                    price_contexts.append({
                        'price': price,
                        'context': context
                    })
                
                if price_contexts:
                    print(f"[SUCCESS] Found {len(price_contexts)} prices with context:\n")
                    
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_contexts = []
                    for pc in price_contexts:
                        key = (pc['price'], pc['context'])
                        if key not in seen:
                            seen.add(key)
                            unique_contexts.append(pc)
                    
                    # Show top 10 with most context
                    for i, pc in enumerate(unique_contexts[:20], 1):
                        print(f"{i}. {pc['price']}")
                        print(f"   Context: ...{pc['context'][:100]}...\n")
                    
                    # For LLM: return full data
                    print(f"[DATA] Returning all {len(unique_contexts)} prices with context for LLM analysis\n")
                    return {
                        'prices_with_context': unique_contexts,
                        'main_price': price_contexts[0]['price'] if price_contexts else None,
                        'full_html_length': len(html)
                    }
                else:
                    print("[FAIL] No prices found")
                    
                    # Debug
                    if "Error" in title or "Oops" in title:
                        print("[WARN] Page appears to be error page")
                    
                    if len(html) < 5000:
                        print(f"\n[DEBUG] Small HTML ({len(html)} chars):")
                        print(html[:500])
                    
                    return None
                
        finally:
            # Stop the profile
            print("[*] Stopping Kameleo profile...")
            client.profile.stop_profile(profile.id)
            print("[OK] Profile stopped\n")
    
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = extract_price_with_kameleo()
    print("\n" + "="*60)
    if result:
        if isinstance(result, dict):
            print(f"SUCCESS: Found {len(result['prices_with_context'])} prices with context")
            print(f"\nTop prices found:")
            for pc in result['prices_with_context'][:5]:
                print(f"  {pc['price']}: {pc['context'][:80]}...")
        else:
            print(f"SUCCESS: EXTRACTED PRICE = {result}")
    else:
        print("FAILED: NO PRICE EXTRACTED")
        print("\nMake sure Kameleo Local API is running on port 5050:")
        print("  C:\\Users\\...\\Kameleo\\Kameleo.CLI.exe")
    print("="*60)
