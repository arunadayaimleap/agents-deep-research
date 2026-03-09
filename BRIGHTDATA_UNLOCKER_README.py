#!/usr/bin/env python3
"""
BRIGHT DATA UNLOCKER INTEGRATION - QUICK REFERENCE
===================================================

## What Changed?

Old: Jina Reader (read_url) → Page extraction
New: Bright Data Unlocker API → Anti-bot bypass + markdown extraction

## Files Updated

1. deep_researcher/tools/brightdata_tools.py
   - Added: brightdata_unlock_url(url, max_length, data_format)
   - Added: BRIGHTDATA_UNLOCKER_ZONE config

2. deep_researcher/tools/web_search.py
   - Replaced: read_url → brightdata_unlock_url
   - In: scrape_urls() and fetch_and_process_url()

3. deep_researcher/tools/crawl_website.py
   - Replaced: read_url → brightdata_unlock_url
   - In: breadth-first crawl loop

4. deep_researcher/agents/tool_agents/crawl_agent.py
   - New: read_url_with_brightdata(@function_tool wrapper)
   - Replaced: read_url_with_jina → read_url_with_brightdata
   - Updated: Agent instructions

5. run_email_pattern_research.py & run_mro_research.py
   - Updated: API key validation (BRIGHTDATA_UNLOCKER_ZONE)
   - Removed: JINA_API_KEY check

6. .env & .env.example
   - Added: BRIGHTDATA_UNLOCKER_ZONE=data_unblocker

## How to Test

### 1. Test Bright Data Unlocker API directly:
   python test_brightdata_unlocker.py

### 2. Test Bright Data SERP (search already tested):
   python test_brightdata.py

### 3. Run email pattern research:
   python run_email_pattern_research.py "Ecopetrol"

### 4. Run batch with 2 companies:
   python run_batch.py --limit 2

## Key Features

- SERP API: Natural language web search (Google results + AI Overview)
- Unlocker API: Anti-bot bypass with markdown conversion
- Both APIs: Single Bright Data account, single API key
- Zones: Can use separate SERP_ZONE and UNLOCKER_ZONE, or shared ZONE as fallback

## Agents Using These Tools

1. WebSearchAgent
   - Tool: web_search() - powered by SERP API
   - Returns: List[ScrapeResult] with markdown content from Unlocker

2. SiteCrawlerAgent
   - Tool: read_url_with_brightdata() - uses Unlocker API directly
   - Returns: Markdown content

3. crawl_website() utility
   - Uses: brightdata_unlock_url() for breadth-first crawl

## Next Steps

1. Verify .env has these variables:
   BRIGHTDATA_API_KEY=<key>
   BRIGHTDATA_SERP_ZONE=serp_api1
   BRIGHTDATA_UNLOCKER_ZONE=data_unblocker

2. Run test to verify Unlocker works:
   python test_brightdata_unlocker.py

3. Run batch research:
   python run_batch.py --limit 2

4. Monitor Bright Data dashboard for usage
"""

if __name__ == "__main__":
    import sys
    print(__doc__)
