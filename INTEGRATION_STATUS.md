# BRIGHT DATA INTEGRATION SUMMARY

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Research Query                            │
│                 (Natural Language)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴──────────────┐
        │                           │
        ▼                           ▼
  ┌─────────────────┐       ┌──────────────────┐
  │ WebSearchAgent  │       │ SiteCrawlerAgent │
  │                 │       │                  │
  │ Tool: web_search│       │ Tool:            │
  │ (SERP API)      │       │ read_url_with_   │
  │                 │       │ brightdata       │
  │ Search Query    │       │ (Unlocker API)   │
  │  ↓              │       │                  │
  │ SERP Results    │       │ Direct URL       │
  │ (5 URLs)        │       │  ↓              │
  │  ↓              │       │ Markdown        │
  └─────────┬───────┘       │ Content         │
            │               └────────┬────────┘
            │                        │
            ▼                        ▼
    ┌──────────────────────────────────────┐
    │   scrape_urls()                      │
    │   Fetch all URLs via Unlocker API    │
    │   (Anti-bot + Markdown conversion)   │
    └──────────────┬───────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────┐
    │     ScrapeResult[]                   │
    │   url, title, description, text      │
    │   (markdown format)                  │
    └──────────────┬───────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────┐
    │   Agent Processing & Summarization   │
    │   (Generate research output)         │
    └──────────────┬───────────────────────┘
                   │
                   ▼
         Final Research Report
```

## Component Overview

### 1. Bright Data SERP API
- **Purpose**: Web search (Google results)
- **Input**: Natural language query (full questions supported)
- **Output**: 5 results with URL, title, description, + AI Overview
- **Zone**: `BRIGHTDATA_SERP_ZONE=serp_api1`
- **Function**: `brightdata_search(query, max_results, include_ai_overview)`

### 2. Bright Data Unlocker API
- **Purpose**: Page extraction with anti-bot bypass
- **Input**: URL
- **Output**: Markdown-formatted page content
- **Zone**: `BRIGHTDATA_UNLOCKER_ZONE=data_unblocker`
- **Function**: `brightdata_unlock_url(url, max_length, data_format="markdown")`
- **Features**:
  - Automatic proxy rotation
  - CAPTCHA solving
  - Blocked content bypass
  - HTML → Markdown conversion

### 3. Web Search Tool Pipeline
```
web_search(query)
    ↓
brightdata_search(query)  [SERP API]
    ↓ [5 search results]
scrape_urls(results)
    ↓
brightdata_unlock_url() for each URL  [Unlocker API]
    ↓
List[ScrapeResult] [markdown content]
```

### 4. Site Crawler Agent
```
read_url_with_brightdata(url)
    ↓
brightdata_unlock_url(url, data_format="markdown")
    ↓
Markdown content
```

### 5. Website Crawl Utility
```
crawl_website(starting_url)
    ↓
BFS queue with brightdata_unlock_url()
    ↓
scrape_urls() for final content extraction
    ↓
List[ScrapeResult] [all discovered pages]
```

## Configuration

```env
# Bright Data Authentication
BRIGHTDATA_API_KEY=9177e7ad-4555-42c6-9092-3fe1a7f20d27

# SERP API (Web Search)
BRIGHTDATA_SERP_ZONE=serp_api1

# Unlocker API (Page Extraction)
BRIGHTDATA_UNLOCKER_ZONE=data_unblocker

# Optional fallback (if SERP_ZONE and UNLOCKER_ZONE not specified)
BRIGHTDATA_ZONE=data_unblocker
```

## File Changes Summary

| File | Change | New Function |
|------|--------|---|
| `brightdata_tools.py` | Added Unlocker API | `brightdata_unlock_url()` |
| `web_search.py` | Jina → Bright Data Unlocker | `scrape_urls()` updated |
| `crawl_website.py` | Jina → Bright Data Unlocker | Crawl loop updated |
| `crawl_agent.py` | New wrapper function | `read_url_with_brightdata()` |
| `run_email_pattern_research.py` | API key validation | Checks `BRIGHTDATA_UNLOCKER_ZONE` |
| `run_mro_research.py` | API key validation | Checks `BRIGHTDATA_UNLOCKER_ZONE` |
| `.env` | Added zone | `BRIGHTDATA_UNLOCKER_ZONE=data_unblocker` |

## Testing Checklist

- [ ] Verify imports: `python -c "from deep_researcher.tools.brightdata_tools import *"`
- [ ] Test Unlocker API: `python test_brightdata_unlocker.py`
- [ ] Test SERP API: `python test_brightdata.py`
- [ ] Test email research: `python run_email_pattern_research.py "Ecopetrol"`
- [ ] Run batch (2 companies): `python run_batch.py --limit 2`
- [ ] Check Bright Data dashboard for usage stats

## Performance Metrics

- SERP Search: 2-5 seconds per query
- Unlocker (page fetch): 5-15 seconds per URL
- Total web search pipeline: 7-20 seconds (search + 1 page fetch)

## Troubleshooting

| Error | Solution |
|-------|----------|
| `BRIGHTDATA_UNLOCKER_ZONE required` | Add to .env: `BRIGHTDATA_UNLOCKER_ZONE=data_unblocker` |
| `Empty response from URL` | Check if URL is blocked or inaccessible |
| `HTTP 401: Unauthorized` | Verify `BRIGHTDATA_API_KEY` is correct |
| `Timeout (120s)` | URL may be slow to respond or unreachable |
| `API quota exceeded` | Check Bright Data dashboard for zone limits |

## Migration Notes

**Removed Dependencies:**
- ~~`JINA_API_KEY`~~ (Jina Reader no longer used)
- ~~`read_url()` from jina_tools~~ (replaced with Unlocker API)
- ~~`jina_search()` from jina_tools~~ (already replaced with SERP)

**Backward Compatibility:**
- Old `.env` files with `JINA_API_KEY` won't break the system
- SERP API already integrated (Jina Search → Bright Data SERP)
- Config remap handles old search provider values

## Next Actions

1. **User runs test**: `python test_brightdata_unlocker.py`
2. **Verify .env is correct**: Check `BRIGHTDATA_UNLOCKER_ZONE`
3. **Run batch research**: `python run_batch.py --limit 2`
4. **Monitor Bright Data dashboard**: Track API usage and quota
