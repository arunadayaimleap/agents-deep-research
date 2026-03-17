#!/usr/bin/env python3
"""
Test script to verify Kameleo Local API is running and working correctly.
Run this before running price comparison workflows.
"""
import sys
import asyncio


def test_kameleo_import():
    """Test if Kameleo SDK is installed."""
    print("[1] Testing Kameleo SDK import...")
    try:
        from kameleo.local_api_client import KameleoLocalApiClient
        from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference
        print("    ✓ Kameleo SDK imported successfully\n")
        return True
    except ImportError as e:
        print(f"    ✗ Kameleo SDK not installed: {e}")
        print("    Install with: pip install kameleo-local-api-client")
        print()
        return False


def test_kameleo_api_connection():
    """Test connection to Kameleo Local API."""
    print("[2] Testing Kameleo Local API connection...")
    try:
        from kameleo.local_api_client import KameleoLocalApiClient
        client = KameleoLocalApiClient(endpoint='http://localhost:5050')
        
        # Try to get fingerprints
        fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
        if not fps:
            print("    ✗ No fingerprints available")
            return False
        
        print(f"    ✓ Connected to Kameleo API")
        print(f"    ✓ Found {len(fps)} available fingerprints\n")
        return True
    except Exception as e:
        print(f"    ✗ Failed to connect to Kameleo API: {e}")
        print("    Make sure Kameleo Local API is running:")
        print("    1. Download Kameleo from https://www.kameleo.io/")
        print("    2. Start it with: kameleo start")
        print("    3. Verify it's running on http://localhost:5050")
        print()
        return False


def test_playwright_import():
    """Test if Playwright is installed."""
    print("[3] Testing Playwright import...")
    try:
        from playwright.async_api import async_playwright
        print("    ✓ Playwright imported successfully\n")
        return True
    except ImportError as e:
        print(f"    ✗ Playwright not installed: {e}")
        print("    Install with: pip install playwright")
        print()
        return False


async def test_kameleo_profile_creation():
    """Test creating a Kameleo profile."""
    print("[4] Testing Kameleo profile creation...")
    try:
        from kameleo.local_api_client import KameleoLocalApiClient
        from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference
        
        client = KameleoLocalApiClient(endpoint='http://localhost:5050')
        
        # Search for fingerprints
        fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
        if not fps:
            print("    ✗ No fingerprints available")
            return False
        
        # Create profile
        profile = client.profile.create_profile(CreateProfileRequest(
            fingerprint_id=fps[0].id,
            name='test-profile'
        ))
        
        print(f"    ✓ Profile created: {profile.id}")
        
        # Start profile
        client.profile.start_profile(profile.id, BrowserSettings(
            arguments=['mute-audio'],
            preferences=[
                Preference(key='profile.default_content_settings.images', value=1),
            ]
        ))
        
        print(f"    ✓ Profile started successfully")
        
        # Stop profile
        client.profile.stop_profile(profile.id)
        print(f"    ✓ Profile stopped successfully\n")
        
        return True
    except Exception as e:
        print(f"    ✗ Profile creation failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_kameleo_with_playwright():
    """Test connecting Playwright to Kameleo profile."""
    print("[5] Testing Kameleo + Playwright integration...")
    try:
        from kameleo.local_api_client import KameleoLocalApiClient
        from kameleo.local_api_client.models import CreateProfileRequest, BrowserSettings, Preference
        from playwright.async_api import async_playwright
        
        client = KameleoLocalApiClient(endpoint='http://localhost:5050')
        
        # Search for fingerprints
        fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
        if not fps:
            print("    ✗ No fingerprints available")
            return False
        
        # Create profile
        profile = client.profile.create_profile(CreateProfileRequest(
            fingerprint_id=fps[0].id,
            name='test-pw-profile'
        ))
        
        print(f"    ✓ Profile created: {profile.id}")
        
        # Start profile
        client.profile.start_profile(profile.id, BrowserSettings(
            arguments=['mute-audio'],
            preferences=[
                Preference(key='profile.default_content_settings.images', value=1),
            ]
        ))
        
        print(f"    ✓ Profile started")
        
        # Connect Playwright
        browser_ws = f'ws://localhost:5050/playwright/{profile.id}'
        print(f"    Connecting to: {browser_ws}")
        
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(endpoint_url=browser_ws)
            print(f"    ✓ Playwright connected to Kameleo profile")
            
            # Get or create context
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = await browser.new_context()
            
            page = await context.new_page()
            print(f"    ✓ Page created")
            
            # Test navigation to a simple page
            try:
                response = await page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=30000)
                print(f"    ✓ Successfully navigated to google.com (status: {response.status if response else 'Unknown'})")
                title = await page.title()
                print(f"    ✓ Page title: {title}")
            except asyncio.TimeoutError:
                print(f"    ⚠ Navigation timed out (may be network issue)")
            
            await page.close()
            await browser.close()
        
        # Stop profile
        client.profile.stop_profile(profile.id)
        print(f"    ✓ Profile cleaned up\n")
        
        return True
    except Exception as e:
        print(f"    ✗ Playwright + Kameleo test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Kameleo Setup Test Suite")
    print("=" * 60)
    print()
    
    results = []
    
    # Sync tests
    results.append(("Kameleo SDK Import", test_kameleo_import()))
    
    if not results[-1][1]:
        print("Kameleo SDK not installed. Install it first.")
        print()
        return False
    
    results.append(("Kameleo API Connection", test_kameleo_api_connection()))
    
    if not results[-1][1]:
        print("Kameleo Local API not running. Start it first.")
        print()
        return False
    
    results.append(("Playwright Import", test_playwright_import()))
    
    if not results[-1][1]:
        print("Playwright not installed. Install it first.")
        print()
        return False
    
    # Async tests
    results.append(("Kameleo Profile Creation", await test_kameleo_profile_creation()))
    results.append(("Kameleo + Playwright Integration", await test_kameleo_with_playwright()))
    
    # Summary
    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Passed: {passed}/{total}")
    print()
    
    if passed == total:
        print("✓ All tests passed! You're ready to run price comparison workflows.")
        return True
    else:
        print("✗ Some tests failed. Please address the issues above.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
