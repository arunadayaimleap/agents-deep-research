# Kameleo Setup & Usage Guide

## Overview

The price comparison workflow now uses **Kameleo** to bypass anti-bot detection on e-commerce sites (Home Depot, Amazon, Walmart, etc.). This guide walks you through setup, testing, and troubleshooting.

---

## Installation

### Prerequisites

- Python 3.10+
- Playwright installed: `pip install playwright`
- Kameleo SDK: `pip install kameleo-local-api-client`
- Kameleo Desktop Application (free tier available)

### Step 1: Download & Install Kameleo Desktop

1. Visit https://www.kameleo.io/download
2. Download the appropriate version for your OS (Windows, macOS, Linux)
3. Install and launch the Kameleo application
4. Create a free account or sign in (free tier includes browser fingerprints)

### Step 2: Start Kameleo Service

**Windows (Command Prompt):**
```bash
kameleo start
```

**macOS/Linux (Terminal):**
```bash
kameleo start
```

You should see output like:
```
[*] Kameleo Local API listening on http://localhost:5050
```

### Step 3: Verify Python Dependencies

```bash
# Install required packages
pip install kameleo-local-api-client playwright beautifulsoup4
```

---

## Testing Kameleo Setup

### Quick Test Script

We provide a comprehensive test script to verify everything is working:

```bash
python test_kameleo_setup.py
```

This will test:
1. Kameleo SDK import
2. Connection to Kameleo Local API
3. Playwright import
4. Profile creation and startup
5. Full Playwright + Kameleo integration
6. Real page navigation

**Expected output:**
```
============================================================
Kameleo Setup Test Suite
============================================================

[1] Testing Kameleo SDK import...
    ✓ Kameleo SDK imported successfully

[2] Testing Kameleo Local API connection...
    ✓ Connected to Kameleo API
    ✓ Found 5 available fingerprints

[3] Testing Playwright import...
    ✓ Playwright imported successfully

[4] Testing Kameleo profile creation...
    ✓ Profile created: <profile-id>
    ✓ Profile started successfully
    ✓ Profile stopped successfully

[5] Testing Kameleo + Playwright integration...
    ✓ Profile created: <profile-id>
    ✓ Profile started
    ✓ Playwright connected to Kameleo profile
    ✓ Page created
    ✓ Successfully navigated to google.com (status: 200)
    ✓ Page title: Google

============================================================
Test Results Summary
============================================================

✓ PASS: Kameleo SDK Import
✓ PASS: Kameleo API Connection
✓ PASS: Playwright Import
✓ PASS: Kameleo Profile Creation
✓ PASS: Kameleo + Playwright Integration

Passed: 5/5

✓ All tests passed! You're ready to run price comparison workflows.
```

---

## Running Price Comparison Workflow

### Basic Usage

```bash
python run_price_comparison.py "https://www.homedepot.com/p/Frigidaire-..." --max-iterations 5
```

### What Happens

1. **Iteration 1**: 
   - Calls `ProductPriceAgent` with the Home Depot URL
   - Kameleo launches a browser with realistic fingerprints
   - Page loads successfully (anti-bot bypass)
   - Extracts: Title, Specs, Current Price
   - Finds competitor products via web search

2. **Iterations 2+**:
   - For each competitor URL found, calls `ProductPriceAgent`
   - Extracts competitor prices
   - Compares and analyzes pricing differences
   - Generates final report

### Expected Tool Output

```
Title: Frigidaire 24-in Front-Control Smart Built-In Tall-Tub...
URL: https://www.homedepot.com/p/...
Specs: 62 dBA | Smart Built-In | Stainless Steel

Current Price: $419.00
Context: ml-2"><span class="sui-text-subtle"><div><span>Was&nbsp;</span><span class="sui-line-through"><span>$519.00...
[Note: Context indicates this may be a sale/discounted price]

Alternate Price: $519.00
Context: span class="sui-line-through"><span>$519.00</span></span></div>
```

---

## Troubleshooting

### Issue 1: "Kameleo is installed but Local API is not running"

**Cause**: Kameleo service not started or not listening on port 5050

**Solution**:
```bash
# Start Kameleo service
kameleo start

# Verify it's running
# Should see: Kameleo Local API listening on http://localhost:5050
```

### Issue 2: "No Kameleo fingerprints available"

**Cause**: 
- Kameleo app not open
- No free fingerprints available in your account
- API version mismatch

**Solution**:
1. Open Kameleo desktop app
2. Log in (create free account if needed)
3. Verify you see fingerprints in the UI
4. Try test again: `python test_kameleo_setup.py`

### Issue 3: "Failed to connect to Kameleo API"

**Cause**: Network issue or wrong endpoint

**Solution**:
1. Check Kameleo is running: `kameleo start`
2. Verify http://localhost:5050 is accessible
3. Check firewall isn't blocking port 5050
4. Restart Kameleo: 
   ```bash
   kameleo stop
   kameleo start
   ```

### Issue 4: "Playwright connection failed"

**Cause**: Playwright may not be installed or outdated

**Solution**:
```bash
pip install --upgrade playwright
playwright install
```

### Issue 5: Page still returns 403 or "Error Page"

**Cause**: Anti-bot protection stronger than Kameleo can bypass, or site-specific JavaScript checks

**Solution**:
1. Update Kameleo to latest version
2. Update browser fingerprints in Kameleo UI
3. Check if site has additional protections (CloudFlare, etc.)
4. Try test on a simpler site first: `python test_kameleo_setup.py`

---

## Architecture

### How Kameleo Integration Works

```
┌─────────────────────────────────────────────────┐
│  run_price_comparison.py                        │
│  (Price comparison workflow)                    │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  ProductPriceAgent                              │
│  (LLM-driven agent)                             │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  get_product_price(url)                         │
│  (Tool function)                                │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  _get_price_via_kameleo(url)                    │
│  (Primary implementation)                       │
└──────────────┬──────────────────────────────────┘
               │
               ├─ KameleoLocalApiClient (API calls)
               │  └─ http://localhost:5050
               │
               ├─ Create profile with fingerprint
               │
               ├─ Start profile (browser instance)
               │
               ├─ Connect via Playwright (async)
               │  └─ Browser with realistic fingerprints
               │
               ├─ Navigate to product URL
               │
               ├─ Extract:
               │  ├─ Title (from h1, meta tags)
               │  ├─ Specs (from spec containers)
               │  └─ Prices (regex + context)
               │
               └─ Stop profile (cleanup)
```

### Fallback Path

If Kameleo not available or fails:

```
get_product_price(url)
    │
    ├─ KAMELEO_AVAILABLE = False
    │
    ▼
_get_price_via_playwright(url)
    │
    ├─ Use PlaywrightManager (may be blocked)
    ├─ Extract basic info
    └─ Return with note: "Kameleo recommended for anti-bot sites"
```

---

## Output Format

### Tool Output Structure

```
Title: <Product Title>
URL: <Product URL>
Specs: <Key specs separated by |>

Current Price: <Price>
Context: <HTML context around price>
[Optional notes about price type]

[Optional] Alternate Price: <Price>
Context: <HTML context>
```

### For LLM Analysis

The context around each price helps the LLM determine:
- **Original Price**: Context contains "Was", "Original", "MSRP", "Was $X"
- **Sale Price**: Context contains "Now", "Save $X", "Discount", "Sale"
- **Current Price**: Most prominently displayed price

Example contexts:
```
Was $519.00  ← Original price (has "Was")
Save $100.00  ← Sale indicator
Now $419.00   ← Current/sale price (has "Now")
```

---

## Best Practices

### 1. **Start Kameleo Before Running Workflows**

Always ensure Kameleo is running:
```bash
kameleo start
# Wait for "Listening on http://localhost:5050"
```

### 2. **Test First**

Before running price comparison on new sites:
```bash
python test_kameleo_setup.py
```

### 3. **Monitor Performance**

Kameleo can take 10-30 seconds per page depending on:
- Site complexity
- Network speed
- Your computer resources

Set appropriate timeouts in price comparison:
```bash
python run_price_comparison.py "https://..." --max-time 300
```

### 4. **Profile Cleanup**

Kameleo profiles are automatically stopped after each request. If you see "Kameleo error" about too many profiles:
```bash
# Restart Kameleo service
kameleo stop
kameleo start
```

### 5. **Update Fingerprints**

Occasionally update fingerprints in Kameleo UI for:
- Better detection evasion
- Latest browser versions
- New anti-bot patterns

---

## Files Modified

- `deep_researcher/tools/browser_tools.py`
  - `_check_kameleo_available()` - Health check
  - `_get_price_via_kameleo()` - Main Kameleo implementation (async)
  - `_get_price_via_playwright()` - Fallback with title/specs extraction

- `deep_researcher/agents/tool_agents/product_price_agent.py`
  - Updated instructions for comprehensive price extraction

- `test_kameleo_setup.py` (NEW)
  - Complete test suite for Kameleo setup

---

## Support & Resources

- **Kameleo Documentation**: https://www.kameleo.io/docs/
- **Playwright Documentation**: https://playwright.dev/python/
- **GitHub Issues**: Report issues in the agents-deep-research repo

---

## Version History

- **v1.0** (Current)
  - Async Kameleo + Playwright integration
  - Title and specs extraction
  - Price context extraction
  - Comprehensive test suite
  - Detailed troubleshooting guide
