#!/usr/bin/env python3
"""
Run deep research to compare prices of a product across competitor ecommerce websites.
Input:  A product URL from any ecommerce site (Amazon, Flipkart, HomeDepot, etc.)
Output: Markdown research report + JSON with competitor product links and prices.

Usage:
  python run_price_comparison.py "https://www.amazon.in/dp/B0C8S6GR8Y"
  python run_price_comparison.py "https://www.amazon.com/dp/B09G9FPHY6" --max-iterations 5
  python run_price_comparison.py "https://www.flipkart.com/apple-iphone-15/p/itm..." --model "deepseek/deepseek-v3.2"

Requires .env with OPENROUTER_API_KEY and BRIGHTDATA_API_KEY (primary for price comparison via BrightData SERP).
SERPER_API_KEY optional fallback.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from deep_researcher import IterativeResearcher, LLMConfig
from agents import set_tracing_disabled

# Disable tracing when OPENAI_API_KEY is placeholder (avoids 401; we use OpenRouter)
if not os.getenv("OPENAI_API_KEY") or "your-" in str(os.getenv("OPENAI_API_KEY", "")):
    set_tracing_disabled(True)


# ---------------------------------------------------------------------------
# Country / competitor mapping
# ---------------------------------------------------------------------------

# Maps known ecommerce domains to their country + top competitor domains
PLATFORM_COMPETITOR_MAP = {
    # India
    "amazon.in":    {"country": "India",         "currency": "INR", "competitors": ["flipkart.com", "croma.com", "reliancedigital.in", "tatacliq.com", "myntra.com", "meesho.com"]},
    "flipkart.com": {"country": "India",         "currency": "INR", "competitors": ["amazon.in", "croma.com", "reliancedigital.in", "tatacliq.com", "meesho.com"]},
    "croma.com":    {"country": "India",         "currency": "INR", "competitors": ["amazon.in", "flipkart.com", "reliancedigital.in", "tatacliq.com"]},
    # USA
    "amazon.com":       {"country": "USA",       "currency": "USD", "competitors": ["walmart.com", "target.com", "bestbuy.com", "ebay.com", "costco.com", "homedepot.com"]},
    "walmart.com":      {"country": "USA",       "currency": "USD", "competitors": ["amazon.com", "target.com", "bestbuy.com", "ebay.com", "costco.com"]},
    "bestbuy.com":      {"country": "USA",       "currency": "USD", "competitors": ["amazon.com", "walmart.com", "target.com", "ebay.com", "costco.com"]},
    "target.com":       {"country": "USA",       "currency": "USD", "competitors": ["amazon.com", "walmart.com", "bestbuy.com", "ebay.com"]},
    "homedepot.com":    {"country": "USA",       "currency": "USD", "competitors": ["amazon.com", "walmart.com", "lowes.com", "target.com"]},
    "lowes.com":        {"country": "USA",       "currency": "USD", "competitors": ["amazon.com", "walmart.com", "homedepot.com", "target.com"]},
    "ebay.com":         {"country": "USA",       "currency": "USD", "competitors": ["amazon.com", "walmart.com", "target.com", "bestbuy.com"]},
    # UK
    "amazon.co.uk":     {"country": "UK",        "currency": "GBP", "competitors": ["ebay.co.uk", "argos.co.uk", "currys.co.uk", "johnlewis.com", "very.co.uk"]},
    "argos.co.uk":      {"country": "UK",        "currency": "GBP", "competitors": ["amazon.co.uk", "ebay.co.uk", "currys.co.uk", "johnlewis.com"]},
    "currys.co.uk":     {"country": "UK",        "currency": "GBP", "competitors": ["amazon.co.uk", "ebay.co.uk", "argos.co.uk", "johnlewis.com"]},
    # Germany
    "amazon.de":        {"country": "Germany",   "currency": "EUR", "competitors": ["ebay.de", "otto.de", "mediamarkt.de", "saturn.de", "idealo.de"]},
    # Australia
    "amazon.com.au":    {"country": "Australia", "currency": "AUD", "competitors": ["ebay.com.au", "jbhifi.com.au", "harveynorman.com.au", "kogan.com", "myer.com.au"]},
    # Canada
    "amazon.ca":        {"country": "Canada",    "currency": "CAD", "competitors": ["walmart.ca", "bestbuy.ca", "canadiantire.ca", "ebay.ca", "thebay.com"]},
    # UAE
    "amazon.ae":        {"country": "UAE",       "currency": "AED", "competitors": ["noon.com", "sharaf-dg.com", "carrefouruae.com", "jumbo.ae"]},
    "noon.com":         {"country": "UAE/KSA",   "currency": "AED", "competitors": ["amazon.ae", "sharaf-dg.com", "carrefouruae.com"]},
}


def detect_platform_info(url: str) -> dict:
    """Detect the platform, country, currency, and competitors from a product URL."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # Strip www.
        domain = hostname.lstrip("www.")
    except Exception:
        domain = ""

    for key, info in PLATFORM_COMPETITOR_MAP.items():
        if domain == key or domain.endswith(f".{key}"):
            return {
                "platform": key,
                "domain": domain,
                "country": info["country"],
                "currency": info["currency"],
                "competitors": info["competitors"],
            }

    # Fallback: unknown platform — use generic global competitors
    return {
        "platform": domain or "unknown",
        "domain": domain,
        "country": "Global",
        "currency": "USD",
        "competitors": ["amazon.com", "ebay.com", "walmart.com", "google.com/shopping"],
    }


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def create_config(model: str = None) -> LLMConfig:
    """Create OpenRouter LLMConfig."""
    m = model or "deepseek/deepseek-v3.2"
    return LLMConfig(
        search_provider="serper",
        reasoning_model_provider="openrouter",
        reasoning_model=m,
        main_model_provider="openrouter",
        main_model=m,
        fast_model_provider="openrouter",
        fast_model=m,
    )


# ---------------------------------------------------------------------------
# Query + Output Instructions
# ---------------------------------------------------------------------------

def build_price_comparison_query(url: str, platform_info: dict) -> str:
    """Build the deep research query for price comparison."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    competitors_str = ", ".join(platform_info["competitors"])

    return (
        f"You are a price comparison research agent. Analysis date: {now}.\n\n"
        f"TARGET PRODUCT URL: {url}\n"
        f"SOURCE PLATFORM: {platform_info['platform']} ({platform_info['country']})\n"
        f"CURRENCY: {platform_info['currency']}\n"
        f"COMPETITOR PLATFORMS TO CHECK: {competitors_str}\n\n"
        f"Your task (follow in order):\n"
        f"1. Visit or search for the target product URL to identify the exact product: "
        f"brand, model name, model number, key specifications (storage, color, size, etc.).\n"
        f"2. Record the source platform's listed price and product title.\n"
        f"3. For each competitor platform listed above, search for the EXACT same product "
        f"(same brand, model number, and key specs — not a similar product) using targeted web searches.\n"
        f"4. For each competitor where you find the product: record the direct product URL and listed price.\n"
        f"5. If a competitor does not carry the exact product, state 'not found' — do NOT substitute a different model.\n"
        f"6. Note any price differences, discounts, or stock status where available.\n"
        f"7. Include a price comparison summary table and strategic insight.\n\n"
        f"Use only real public sources. Do NOT invent prices or URLs.\n"
        f"Cite all claims with URLs."
    )


def _get_output_instructions() -> str:
    """Output format instructions for the writer agent."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    return f"""
**Analysis date: {date_str} {time_str}**

Your response MUST have two distinct sections in this order:

1. **Report** (## Report):
   A comprehensive markdown price comparison report with these sections:
   1. Product Identification (exact product name, brand, model number, key specs)
   2. Source Platform Price (platform name, price, currency, stock status, URL)
   3. Competitor Price Findings (one subsection per competitor checked, with URL and price — or "not found")
   4. Price Comparison Table (markdown table: Platform | Price | Currency | Stock | URL)
   5. Best Deal Summary (which platform is cheapest, % savings vs source)
   6. Research Notes (data gaps, confidence, sources used)

   **Requirements:**
   - Use the EXACT product URL from each competitor's website — not a search results page.
   - Include real prices in the local currency of the source platform.
   - Use a markdown table for the price comparison.
   - Cite every claim with [1], [2], etc. and include a full references list at the end.
   - Do NOT invent or estimate prices. If a price cannot be confirmed, mark it as "Unconfirmed".

2. **JSON Output** (## JSON Output):
   A valid JSON block matching exactly this schema:
{{
  "metadata": {{
    "input_url": "...",
    "product_name": "...",
    "brand": "...",
    "model_number": "...",
    "key_specs": "...",
    "source_platform": "...",
    "country": "...",
    "currency": "...",
    "analysis_date": "{date_str}"
  }},
  "source_product": {{
    "platform": "...",
    "url": "...",
    "price": "...",
    "currency": "...",
    "in_stock": true,
    "confidence": "high | medium | low"
  }},
  "competitor_results": [
    {{
      "platform": "...",
      "url": "...",
      "price": "...",
      "currency": "...",
      "in_stock": true,
      "found": true,
      "confidence": "high | medium | low",
      "notes": "..."
    }}
  ],
  "best_deal": {{
    "platform": "...",
    "price": "...",
    "savings_vs_source": "..."
  }}
}}

If a competitor does not carry the product, set "found": false and "price": null, "url": null.
Do NOT fabricate prices or product URLs.
"""


# ---------------------------------------------------------------------------
# JSON Extraction
# ---------------------------------------------------------------------------

def extract_json_from_report(report: str) -> dict | None:
    """Extract the price comparison JSON from the report."""
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', report)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace_match = re.search(r'\{[\s\S]*"competitor_results"[\s\S]*\}', report)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    return re.sub(r'[^\w\-]', '_', s.lower())[:40]


def _timestamped_basename(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain_slug = _slug(parsed.hostname or "unknown")
        path_slug = _slug(parsed.path.strip("/").split("/")[-1] or "product")
    except Exception:
        domain_slug = "unknown"
        path_slug = "product"
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"price_comparison_{domain_slug}_{path_slug}_{ts}"


# ---------------------------------------------------------------------------
# Core research runner
# ---------------------------------------------------------------------------

async def run_research(
    url: str,
    max_iterations: int = 5,
    max_time: int = 60,
    model: str | None = None,
) -> tuple[str, dict | None]:
    """Run price comparison research and return (report, extracted_json)."""
    platform_info = detect_platform_info(url)

    print(f"\n[*] Source platform  : {platform_info['platform']} ({platform_info['country']})")
    print(f"[$] Currency         : {platform_info['currency']}")
    print(f"[>] Competitors      : {', '.join(platform_info['competitors'])}\n")

    query = build_price_comparison_query(url, platform_info)
    config = create_config(model=model)

    researcher = IterativeResearcher(
        max_iterations=max_iterations,
        max_time_minutes=max_time,
        verbose=True,
        tracing=False,
        config=config,
    )

    report = await researcher.run(
        query,
        output_length="3-5 pages",
        output_instructions=_get_output_instructions(),
    )

    extracted = extract_json_from_report(report)
    return report, extracted


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Deep price comparison research for any ecommerce product URL"
    )
    parser.add_argument("url", help="Full product URL (e.g. https://www.amazon.in/dp/B0C8S6GR8Y)")
    parser.add_argument("--model", "-m", default="deepseek/deepseek-v3.2", help="LLM model (default: deepseek/deepseek-v3.2)")
    parser.add_argument("--max-iterations", "-i", type=int, default=5, help="Max research iterations (default: 5)")
    parser.add_argument("--max-time", "-t", type=int, default=60, help="Max time in minutes (default: 60)")
    parser.add_argument("--output", "-o", help="Output .md file path (default: outputs/<slug>.md)")
    parser.add_argument("--json-only", action="store_true", help="Print only the extracted JSON")
    args = parser.parse_args()

    if not (os.getenv("BRIGHTDATA_API_KEY") or os.getenv("SERPER_API_KEY")):
        print("Error: Set BRIGHTDATA_API_KEY (recommended) or SERPER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Error: Set OPENROUTER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Price Comparison Research ===")
    print(f"URL   : {args.url}")
    print(f"Model : {args.model}\n")

    report, extracted = asyncio.run(run_research(
        args.url,
        max_iterations=args.max_iterations,
        max_time=args.max_time,
        model=args.model,
    ))

    if args.json_only and extracted:
        print(json.dumps(extracted, indent=2, ensure_ascii=False))
        return

    if args.json_only and not extracted:
        print("Could not extract JSON from report.", file=sys.stderr)
        sys.exit(1)

    # Save outputs
    out_dir = _project_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    base = _timestamped_basename(args.url)
    out_path = Path(args.output) if args.output else (out_dir / f"{base}.md")
    out_path.write_text(report, encoding="utf-8")
    print(f"\n=== Report saved to {out_path} ===\n")

    if extracted:
        json_path = out_path.with_suffix(".json")
        json_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON saved to {json_path}")

        # Print competitor results summary
        if "competitor_results" in extracted:
            print("\n[=] Competitor Price Summary:")
            print(f"{'Platform':<25} {'Price':<15} {'Found':<8} URL")
            print("-" * 90)
            source = extracted.get("source_product", {})
            print(f"{'[SOURCE] ' + source.get('platform',''):<25} {source.get('price','?'):<15} {'Y':<8} {source.get('url','')[:50]}")
            for r in extracted["competitor_results"]:
                found_icon = "Y" if r.get("found") else "N"
                price = r.get("price") or "not found"
                print(f"{r.get('platform',''):<25} {str(price):<15} {found_icon:<8} {str(r.get('url') or '')[:50]}")

        if "best_deal" in extracted and extracted["best_deal"]:
            bd = extracted["best_deal"]
            print(f"\n[!] Best Deal: {bd.get('platform')} at {bd.get('price')} ({bd.get('savings_vs_source')} savings)")

    print("\n=== Full Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
