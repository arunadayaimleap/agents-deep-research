# BrightData SERP Integration — Todo

## Phase 1: Test & Validate
- [x] Read BrightData SERP AI Overview docs
- [x] Write test script (`test_brightdata_serp.py`)
- [x] Find correct SERP zone name from account
- [x] Run live test & confirm response structure (organic, shopping, ai_overview)
- [x] Confirm `extract_llm_payload()` strips images correctly & produces usable LLM context

## Phase 2: Build the Tool
- [x] Create `deep_researcher/tools/brightdata_serp.py` — `@function_tool brightdata_serp_search(query, country)`
  - POST to BrightData API with `zone=<serp_zone>`, Google search URL with `brd_json=1&brd_ai_overview=2`
  - Strip base64 images from response
  - Return clean JSON string (organic + shopping + ai_overview + PAA) for LLM
- [x] Add `BRIGHTDATA_SERP_ZONE` to `.env`

## Phase 3: Build the Agent
- [x] Create `deep_researcher/agents/tool_agents/serp_agent.py` — `BrightDataSERPAgent`
  - Single tool: `brightdata_serp_search`
  - Instructions: dump full raw result to analysis, extract product name, price, URL, country
  - One search at a time (per competitor) for quality
- [x] Register in `tool_agents/__init__.py`

## Phase 4: Redesign the Price Comparison Flow
Update `run_price_comparison.py` and `tool_selector_agent.py` with new flow:

**Step 1 — Source Product Discovery (1 search)**
- Query: `"<product name from URL> exact specifications price"`
- From results: extract product name, model, specs, source price, country/currency

**Step 2 — Competitor Identification (1 search)**
- Query: `"top competitors of <source platform> in <country>"`
- From results: extract top 3-5 competitor platforms + domains

**Step 3 — Competitor Price Search (1 search PER competitor, sequential)**
- Query: `"<product name> <model> site:<competitor domain>"`
- Each search dumps full raw JSON to LLM → LLM extracts: price, URL, availability
- RESTRICTION: Do ONE competitor at a time — parallel searches reduce result quality

## Phase 5: Update Tool Selector Agent
- [x] Replace WebSearchAgent description with BrightDataSERPAgent
- [x] Add constraint: search competitors ONE AT A TIME
- [x] Remove Jina jina_search references (already done)

## Phase 6: Verification
- [x] Run `python test_brightdata_serp.py` and confirm shopping/organic results
- [ ] Run `python run_price_comparison.py "<test URL>"` end-to-end
- [ ] Verify JSON output has correct prices from each competitor
