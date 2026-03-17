#!/usr/bin/env python3
"""
Simple price extraction using requests + BeautifulSoup.
Copy the page HTML and save it, then this script will extract the price.
"""
import re

# For now, this is a manual process:
# 1. Open Chrome normally
# 2. Go to: https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606
# 3. Wait for page to load
# 4. Right-click > "Save as..." > Save as HTML file to "homedepot_page.html"
# 5. Run this script

def extract_price_from_file(filename="homedepot_page.html"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            html = f.read()
        
        print(f"[OK] Loaded {len(html)} chars from {filename}\n")
        
        # Look for price patterns
        prices = re.findall(r'\$[\d,]+\.?\d*', html)
        
        if prices:
            unique = list(set(prices))
            print(f"[SUCCESS] Found {len(unique)} unique prices:")
            for p in unique[:20]:  # Show first 20
                print(f"  - {p}")
            
            print(f"\n[MAIN] Primary price: {prices[0]}")
            return prices[0]
        else:
            print("[FAIL] No prices found in HTML")
            
            # Check if it's error page
            if "Oops" in html or "Error" in html:
                print("[WARN] Page appears to be an error page")
            
            # Show first 500 chars for debugging
            print(f"\nFirst 500 chars of HTML:\n{html[:500]}")
            return None
            
    except FileNotFoundError:
        print(f"[ERROR] File not found: {filename}")
        print("\nInstructions:")
        print("1. Open Chrome and go to:")
        print("   https://www.homedepot.com/p/Frigidaire-24-in-Front-Control-Smart-Built-In-Tall-Tub-62-dBA-Dishwasher-in-Stainless-Steel-FDPC4221AS/314298606")
        print("2. Wait for page to fully load")
        print("3. Right-click > 'Save as...' > Choose 'Web Page, HTML only' > Save as 'homedepot_page.html'")
        print("4. Run this script again")
        return None

if __name__ == "__main__":
    print("=== Home Depot Price Extraction ===\n")
    price = extract_price_from_file()
    print("\n" + "="*50)
    if price:
        print(f"EXTRACTED PRICE: {price}")
    else:
        print("NO PRICE EXTRACTED - See instructions above")
    print("="*50)
