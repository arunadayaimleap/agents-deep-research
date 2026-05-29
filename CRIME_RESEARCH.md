# Criminal Case News Research

Deep iterative research on **top criminal cases in today's news**, using OpenRouter for LLM calls and for retrieval (`openrouter:web_search`, `openrouter:web_fetch`).

## Setup

```env
OPENROUTER_API_KEY=sk-or-...
SEARCH_PROVIDER=openrouter
```

## CLI

```bash
# Top 5 cases globally (default)
python run_crime_research.py

# US-focused, 3 cases
python run_crime_research.py --region US --max-cases 3

# Single case
python run_crime_research.py --case "Example case headline" --region US

# JSON only
python run_crime_research.py --region US --json-only
```

Outputs: `outputs/crime_top_cases_<region>_<timestamp>.md` and matching `.json`.

## API

```bash
pm2 start ecosystem.config.cjs
```

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"region":"US","max_cases":5}'
```

Poll `GET /research/{task_id}/status` then `GET /research/{task_id}/report`.

## Notes

- Reports label **allegations** vs established facts.
- Search is limited to public news and official sources.
- Requires network access and OpenRouter credits for search/fetch.
