# Email Pattern Research for Colombian Companies

This module runs deep research on Colombian companies to discover their corporate email patterns. The output is designed for saving to `ord_email_patterns` (formula, primary_pattern, primary_confidence).

## Setup

1. Add to `.env`:
   ```
   OPEN_ROUTER_KEY=<your-openrouter-key>
   SERPER_DEV_API_KEY=<your-serper-dev-api-key>
   ```
   Or use `OPENROUTER_API_KEY` / `SERPER_API_KEY` if preferred.

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```bash
# Basic - research Ecopetrol
python run_email_pattern_research.py "Ecopetrol"

# With domain hint
python run_email_pattern_research.py "Bancolombia" --domain bancolombia.com.co

# More iterations and time
python run_email_pattern_research.py "Grupo Aval" --max-iterations 5 --max-time 15

# Save to custom path
python run_email_pattern_research.py "Ecopetrol" -o output/ecopetrol.md

# Extract JSON only (for piping)
python run_email_pattern_research.py "Ecopetrol" --json-only
```

## Output

- **Report**: `outputs/<company>_email_pattern_report.md` with:
  1. Reasoning
  2. Research summary
  3. Full report with citations
  4. JSON block (metadata, formula_dominante, detalles, ejemplo_emails, ord_email_patterns)

- **JSON**: `outputs/<company>_email_pattern_report.json` with the extracted structured data

## ord_email_patterns Schema

The `ord_email_patterns` object in the JSON matches the database schema:

```json
{
  "formula": [["first.last", 90, true], ["firstlast", 70, false]],
  "primary_pattern": "first.last",
  "primary_confidence": 90
}
```

- `formula`: Array of `[patron, confidence, recommended]`
- `primary_pattern`: Best pattern or "No detectada"
- `primary_confidence`: 0-100 (0 if no pattern found)

## Prompt

Custom prompt is in `prompts/email_pattern_research.txt`.
