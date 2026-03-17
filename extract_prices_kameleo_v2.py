#!/usr/bin/env python3
"""
Extract Home Depot prices with full context using Kameleo + Playwright.
Finds original and sale prices by analyzing surrounding HTML.
"""
import re
import json
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference
from playwright.sync_api import sync_playwright

URL = "https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606"

def extract_prices_with_kameleo():
    print("=== Extracting Home Depot Prices with Kameleo ===\n")
    print(f"URL: {URL}\n")
    
    client = KameleoLocalApiClient(endpoint='http://localhost:5050')
    
    try:
        # Step 1: Search fingerprints
        print("[1] Searching for Chrome fingerprints...")
        fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
        print(f"    Found {len(fps)} fingerprints\n")
        
        # Step 2: Create profile
        print("[2] Creating Kameleo profile...")
        profile = client.profile.create_profile(CreateProfileRequest(
            fingerprint_id=fps[0].id,
            name='homedepot-price-extraction'
        ))
        print(f"    Profile ID: {profile.id}\n")
        
        # Step 3: Start profile with custom settings
        print("[3] Starting profile with optimized settings...")
        client.profile.start_profile(profile.id, BrowserSettings(
            arguments=['mute-audio'],
            preferences=[
                Preference(key='profile.default_content_settings.images', value=1),  # Allow images
            ]
        ))
        print("    Profile started\n")
        
        # Step 4: Connect with Playwright
        print("[4] Connecting Playwright...")
        browser_ws = f'ws://localhost:5050/playwright/{profile.id}'
        
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(endpoint_url=browser_ws)
            context = browser.contexts[0]
            page = context.new_page()
            
            print("[5] Navigating to URL...")
            response = page.goto(URL, wait_until='networkidle', timeout=90000)
            
            status = response.status if response else "Unknown"
            title = page.title()
            print(f"    Status: {status}")
            print(f"    Title: {title}\n")
            
            # Step 6: Wait for full render
            print("[6] Waiting for page to fully render...")
            page.wait_for_timeout(5000)
            
            # Step 7: Extract HTML
            print("[7] Extracting page HTML...")
            html = page.content()
            print(f"    Got {len(html):,} characters\n")
            
            # Step 8: Extract prices with detailed context
            print("[8] Analyzing prices with context...\n")
            
            price_pattern = r'.{0,100}(\$[\d,]+\.?\d*).{0,100}'
            matches = re.finditer(price_pattern, html, re.DOTALL)
            
            prices_with_context = []
            for match in matches:
                price = match.group(1)
                context = match.group(0).replace('\n', ' ').replace('\t', ' ')
                context = ' '.join(context.split())  # Normalize whitespace
                
                prices_with_context.append({
                    'price': price,
                    'context': context,
                    'context_preview': context[:80] + '...' if len(context) > 80 else context
                })
            
            # Remove duplicates
            seen = set()
            unique_prices = []
            for pc in prices_with_context:
                key = (pc['price'], pc['context'])
                if key not in seen:
                    seen.add(key)
                    unique_prices.append(pc)
            
            # Sort by price amount (convert to float for sorting)
            def price_to_float(p):
                try:
                    return float(p['price'].replace('$', '').replace(',', ''))
                except:
                    return 0
            
            unique_prices.sort(key=price_to_float, reverse=True)
            
            # Display top prices
            print(f"Found {len(unique_prices)} prices with context:\n")
            for i, pc in enumerate(unique_prices[:20], 1):
                print(f"{i}. {pc['price']}")
                print(f"   {pc['context_preview']}\n")
            
            # Extract likely product price (usually 100+ dollars for dishwasher)
            main_prices = [p for p in unique_prices if price_to_float(p) > 100]
            
            print("="*60)
            if main_prices:
                print(f"TOP PRODUCT PRICES (>$100):\n")
                for pc in main_prices[:5]:
                    print(f"  {pc['price']}: {pc['context_preview']}")
                print(f"\nLikely main price: {main_prices[0]['price']}")
            
            # Save full data to JSON for LLM analysis
            output_data = {
                'url': URL,
                'html_length': len(html),
                'total_prices_found': len(unique_prices),
                'prices': unique_prices
            }
            
            json_output = json.dumps(output_data, indent=2)
            with open('homedepot_prices.json', 'w') as f:
                f.write(json_output)
            
            print(f"\nFull data saved to homedepot_prices.json")
            print("="*60)
            
            return output_data
        
    finally:
        # Cleanup
        print("\n[Cleanup] Stopping profile...")
        client.profile.stop_profile(profile.id)
        print("Profile stopped")

if __name__ == "__main__":
    try:
        result = extract_prices_with_kameleo()
        if result:
            print(f"\n[SUCCESS] Extracted {result['total_prices_found']} prices")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
