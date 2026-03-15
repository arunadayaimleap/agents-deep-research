# Legal Research Agent Workflow

## Agent

`LegalResearchAgent`

### Role

Analyze each judgment and produce **structured legal knowledge**.

### Inputs

```text
judgment_id
judgment_text
paragraphs[]
existing_case_database
```

### Outputs

```text
case_metadata
citations
citation_relationships
statutes
issues
ratio
headnotes
taxonomy_tags
case_summary
citation_graph_updates
```

---

# Tools Available to the Legal Research Agent

## 1️⃣ Citation Extraction Tool

**Purpose**

Detect all cases cited in the judgment.

### Method

- regex patterns

- citation NER

- legal citation dictionaries

### Output

```json
[
  {
    "citation_text": "(1996) 2 SCC 384",
    "case_name": "State of Punjab v Gurmit Singh",
    "paragraph": 34
  }
]
```

---

## 2️⃣ Citation Resolver Tool

**Purpose**

Map citation strings to canonical case records.

### Example

Resolve:

```
AIR 1996 SC 1393
(1996) 2 SCC 384
```

to one case ID.

### Tool operations

- search internal case DB

- web search fallback if missing

---

## 3️⃣ Precedent Relationship Classifier

**Purpose**

Determine how the cited case is used.

### Output

```json
{
  "source_case": "Case A",
  "target_case": "Case B",
  "relationship": "RELIES_ON"
}
```

### Possible relationships

```
RELIES_ON
FOLLOWS
DISTINGUISHES
OVERRULES
REFERS_TO
APPLIES
```

---

## 4️⃣ Statute Extraction Tool

Detect statutory references such as:

- Indian Penal Code

- Code of Criminal Procedure

- Constitution of India

### Output

```json
[
  {
    "statute": "Indian Penal Code",
    "section": "302",
    "paragraph": 17
  }
]
```

---

## 5️⃣ Issue Detection Tool

Extract the **legal questions addressed**.

Example output:

```json
[
  "Whether delay in FIR affects prosecution credibility"
]
```

---

## 6️⃣ Ratio Extraction Tool

Identify the **binding legal principle**.

Output:

```json
{
  "ratio": "Delay in FIR does not invalidate prosecution evidence if adequately explained",
  "supporting_paragraphs": [41, 42]
}
```

---

## 7️⃣ Headnote Generator

Create SCC-style headnotes.

Example:

```
Criminal Law — Evidence — FIR — Delay —
Delay explained satisfactorily — Conviction upheld.
```

---

## 8️⃣ Legal Topic Classifier

Map case to taxonomy nodes.

Example:

```json
[
  "Criminal Law",
  "Evidence",
  "FIR Delay"
]
```

Implementation options:

- embedding similarity

- LLM classification

- hybrid approach

---

## 9️⃣ Case Summary Generator

Produce concise research summaries.

Example:

```text
The Supreme Court held that delay in filing FIR
does not necessarily weaken the prosecution case
where the delay is satisfactorily explained.
```

---

## 🔟 Citation Graph Tool

Update precedent graph.

Example edge:

```json
{
  "source_case": "Case A",
  "target_case": "Case B",
  "relationship": "RELIES_ON"
}
```

Stored in graph DB or adjacency tables.

---

# Full Agent Execution Flow

```
LegalResearchAgent
      │
      ▼
Extract case metadata
      │
      ▼
Run Citation Extraction Tool
      │
      ▼
Resolve citations
      │
      ▼
Classify precedent relationships
      │
      ▼
Extract statutes
      │
      ▼
Identify legal issues
      │
      ▼
Extract ratio decidendi
      │
      ▼
Generate headnotes
      │
      ▼
Assign legal taxonomy
      │
      ▼
Generate case summary
      │
      ▼
Update citation graph
      │
      ▼
Save structured case record
```

---

# Additional Tools

These can make your system much stronger.

### Paragraph Importance Tool

Ranks paragraphs by legal significance.

Helps identify:

- ratio paragraphs

- key reasoning

---

### Fact Pattern Extractor

Extracts structured facts.

Example:

```json
{
  "crime": "murder",
  "weapon": "knife",
  "key_issue": "dying declaration reliability"
}
```

This enables **fact-pattern search** later.

---

### Case Evolution Tool

Tracks later treatment of the case:

```
followed
distinguished
overruled
```

This keeps precedents **up to date**.
