# Bright Data Unlocker API Integration

## Summary

Replaced Jina Reader with **Bright Data Unlocker API** for page extraction and content scraping across the entire system.

**Benefits:**
- Anti-bot bypass and CAPTCHA handling
- Automatic proxy management
- Markdown content conversion (cleaner than raw HTML)
- Better handling of JavaScript-heavy sites
- Integrated with existing Bright Data SERP API (single provider)

## Files Modified

### 1. **deep_researcher/tools/brightdata_tools.py**
- Added `BRIGHTDATA_UNLOCKER_ZONE` configuration
- New async function: `brightdata_unlock_url(url, max_length, data_format)`
  - Calls Bright Data Unlocker API with `format: "json"` and `data_format: "markdown"`
  - Returns clean markdown content (up to `max_length` chars)
  - Handles errors gracefully with descriptive messages

### 2. **deep_researcher/tools/web_search.py**
- Import: Replaced `from .jina_tools import read_url` with `from .brightdata_tools import brightdata_unlock_url`
- Updated `fetch_and_process_url()` to call `brightdata_unlock_url()` instead of `read_url()`
- Updated docstrings to reference Bright Data Unlocker

### 3. **deep_researcher/tools/crawl_website.py**
- Import: Replaced `from .jina_tools import read_url` with `from .brightdata_tools import brightdata_unlock_url`
- Updated breadth-first crawl loop to call `brightdata_unlock_url()` instead of `read_url()`

### 4. **deep_researcher/agents/tool_agents/crawl_agent.py**
- Created new wrapper function: `read_url_with_brightdata(url)` using `@function_tool` decorator
  - Calls `brightdata_unlock_url()` internally
- Replaced tool import from Jina to new wrapper
- Updated instructions to reference "Bright Data Unlocker" and `read_url_with_brightdata`

### 5. **run_email_pattern_research.py**
- Updated API key validation:
  - Check for `BRIGHTDATA_UNLOCKER_ZONE` (or fallback to `BRIGHTDATA_ZONE`)
  - Removed check for `JINA_API_KEY`
- Updated docstring to reflect new dependencies

### 6. **run_mro_research.py**
- Updated API key validation:
  - Check for `BRIGHTDATA_UNLOCKER_ZONE` (or fallback to `BRIGHTDATA_ZONE`)
  - Removed check for `JINA_API_KEY`

### 7. **.env.example**
- Updated documentation for Bright Data configuration:
  - `BRIGHTDATA_API_KEY` (for both SERP and Unlocker)
  - `BRIGHTDATA_SERP_ZONE` (for web search)
  - `BRIGHTDATA_UNLOCKER_ZONE` (for page extraction)
  - Removed `JINA_API_KEY` entries
  - Added note about `BRIGHTDATA_ZONE` fallback

### 8. **.env**
- Added `BRIGHTDATA_UNLOCKER_ZONE=data_unblocker`
- Kept existing `BRIGHTDATA_API_KEY` and zones

## New Files

### **test_brightdata_unlocker.py**
Smoke test for Bright Data Unlocker API integration.

**Usage:**
```bash
python test_brightdata_unlocker.py
```

**Tests:**
- Markdown extraction from https://example.com
- Markdown extraction from https://www.python.org
- Markdown extraction from https://drummondltd.com/en/

## Configuration

### .env Requirements

```env
# Required for both SERP and Unlocker
BRIGHTDATA_API_KEY=<your-api-key>

# Web search (SERP API)
BRIGHTDATA_SERP_ZONE=serp_api1

# Page extraction (Unlocker API)
BRIGHTDATA_UNLOCKER_ZONE=data_unblocker

# Optional fallback if UNLOCKER_ZONE/SERP_ZONE not set
BRIGHTDATA_ZONE=data_unblocker
```

## Workflow

### Web Search → Page Extraction Pipeline

1. **Web Search** (SERP API):
   - Natural language query support
   - Returns top 5 results with title, description, URL
   - Includes Google AI Overview if available

2. **Page Extraction** (Unlocker API):
   - Fetches URLs from search results
   - Bypasses anti-bot protections
   - Converts HTML to clean markdown
   - Returns content (max 10,000 chars)

3. **Agent Processing**:
   - WebSearchAgent uses `web_search()` tool
   - SiteCrawlerAgent uses `read_url_with_brightdata()` tool
   - crawl_website() utility uses Unlocker API for breadth-first traversal

## Testing

### Test Unlocker API:
```bash
python test_brightdata_unlocker.py
```

Expected output:
```
Testing Bright Data Unlocker API with markdown conversion...

Fetching: https://example.com
  ✓ Success, content length: 500 chars
  Preview: # Example Domain...

Fetching: https://www.python.org
  ✓ Success, content length: 500 chars
  Preview: # Welcome to Python.org...

Fetching: https://drummondltd.com/en/
  ✓ Success, content length: 500 chars
  Preview: [content preview]...
```

### Run Full Batch:
```bash
python run_batch.py --limit 2
```

### Run Single Company Research:
```bash
python run_email_pattern_research.py "Ecopetrol"
```

## Removed Dependencies

- ~~Jina Reader API (read_url function)~~
- ~~Jina Search API (jina_search function)~~

**Note:** Jina tools file still exists but is no longer used by main agents.

## API Rate Limits & Pricing

**Bright Data Unlocker:**
- Zone-based pricing (concurrent requests)
- Automatic proxy rotation
- CAPTCHA solving included
- Typical response time: 5-15 seconds per page

**Bright Data SERP:**
- Per-request pricing
- Natural language query support
- AI Overview extraction
- Typical response time: 2-5 seconds per search

## Troubleshooting

### Error: "BRIGHTDATA_UNLOCKER_ZONE required"
```
Solution: Add BRIGHTDATA_UNLOCKER_ZONE to .env
```

### Error: "Empty response from URL"
```
Possible causes:
1. URL is inaccessible (404, 403, etc.)
2. Content blocked by anti-bot protection
3. Zone quota exceeded

Solution: Check zone settings in Bright Data dashboard
```

### Timeout (120 seconds)
```
Solution: Increase max_length limit or check network connectivity
```

## Next Steps

1. Test with `python test_brightdata_unlocker.py`
2. Verify .env has `BRIGHTDATA_UNLOCKER_ZONE` set
3. Run batch: `python run_batch.py --limit 2`
4. Monitor Bright Data dashboard for API usage and quota
