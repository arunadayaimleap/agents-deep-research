# 🏗️ Architecture Documentation — `agents-deep-research`

> A deep research assistant built on the **OpenAI Agents SDK**, using a multi-agent, iterative agentic loop to research any topic and produce structured intelligence reports.

---

## Table of Contents

1. [High-Level Overview](#high-level-overview)
2. [Two Research Modes](#two-research-modes)
3. [Flow Diagrams](#flow-diagrams)
   - [IterativeResearcher Flow](#iterativeresearcher-flow)
   - [DeepResearcher Flow](#deepresearcher-flow)
   - [MRO Report End-to-End Flow](#mro-report-end-to-end-flow)
4. [Component Diagram](#component-diagram)
5. [Component Reference](#component-reference)
   - [Entry Points](#entry-points)
   - [Core Orchestrators](#core-orchestrators)
   - [Agents](#agents)
   - [Tool Agents](#tool-agents)
   - [Tools (Underlying Integrations)](#tools-underlying-integrations)
   - [LLM Configuration](#llm-configuration)
6. [Search Integration: How Serper Works](#search-integration-how-serper-works)
7. [How to Extend: Adding a Custom Tool Agent](#how-to-extend-adding-a-custom-tool-agent)
8. [Data Flow: One Research Iteration](#data-flow-one-research-iteration)
9. [File Structure Reference](#file-structure-reference)

---

## High-Level Overview

This is **not a simple chatbot**. It is a fully autonomous, multi-agent research system. When you give it a query, it:

1. Repeatedly identifies what it **doesn't know yet** (knowledge gaps)
2. Selects the right **specialized agents** to fill those gaps  
3. Runs those agents **in parallel** to gather real web data
4. **Reflects** on the findings to steer the next iteration
5. Produces a **final structured report** (Markdown + JSON)

The system is built on top of the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python), which provides the underlying agent execution, tracing, and tool-calling runtime. All LLM providers (OpenRouter, DeepSeek, Gemini, Anthropic, etc.) are accessed through the same OpenAI-spec API wrapper.

**No MCP (Model Context Protocol).** Serper and all other integrations are plain Python HTTP calls, wrapped as `@function_tool` callables that the OpenAI Agents SDK registers as tools for agents.

---

## Two Research Modes

| Mode                   | Class                 | Best For                                                                                                                    |
| ---------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Simple / Iterative** | `IterativeResearcher` | Short to medium reports (up to ~5 pages). Runs a continuous loop.                                                           |
| **Deep**               | `DeepResearcher`      | Long, structured reports (20+ pages). Plans sections first, then runs parallel `IterativeResearcher` instances per section. |

Both can be used via Python, CLI (`deep-researcher`), or the FastAPI REST API (`api.py`).

---

## Flow Diagrams

### IterativeResearcher Flow

This is the core loop. Everything — including the `DeepResearcher` — is powered by this.

```mermaid
flowchart TD
    A["User / Entry Point\n(run_mro_research.py, api.py, CLI)"]
    A --> B["build_mro_query()\nBuilds structured natural language\nresearch query from inputs"]
    B --> C["IterativeResearcher.run()\nOrchestrates the entire loop"]

    subgraph Loop["🔄 Research Loop (max_iterations / max_time)"]
        direction TB
        C1["Thinking Agent\n(generate_observations)\nReflects on current state\nand prior findings"] --> C2
        C2["Knowledge Gap Agent\n(evaluate_gaps)\nIdentifies what is still unknown\nOutputs: KnowledgeGapOutput"] --> C3
        C3{Research\ncomplete?}
        C3 -- No --> C4
        C3 -- Yes --> C7
        C4["Tool Selector Agent\n(select_agents)\nDecides which agents to call\nand with what queries\nOutputs: AgentSelectionPlan"] --> C5
        C5["Execute Tools\n(run concurrently via asyncio)\nWebSearchAgent | SiteCrawlerAgent | ..."] --> C6
        C6["Findings appended\nto Conversation history"] --> C1
    end

    C --> Loop
    C7["Writer Agent\n(create_final_report)\nSynthesizes all findings\ninto the final report"] --> D["Save outputs/\n*.md + *.json"]
```

---

### DeepResearcher Flow

```mermaid
flowchart TD
    A["User Query"]
    A --> B["Planner Agent\nBreaks query into report sections:\n- Title\n- Section headings\n- Key question per section\n- Background context"]
    B --> C

    subgraph Parallel["⚡ Parallel Section Research (asyncio.gather)"]
        direction LR
        C["Section 1\nIterativeResearcher"]
        D["Section 2\nIterativeResearcher"]
        E["Section N\nIterativeResearcher"]
    end

    C --> F["Section Draft 1"]
    D --> F2["Section Draft 2"]
    E --> FN["Section Draft N"]

    F & F2 & FN --> G["Long Writer Agent / Proofreader Agent\nAssembles all section drafts\ninto a coherent final report"]
    G --> H["Final Report (Markdown)"]
```

---

### MRO Report End-to-End Flow

This is the concrete flow for `run_mro_research.py` — your MRO-specific entry point.

```mermaid
flowchart LR
    U["CLI / API Call\npython run_mro_research.py\n'Boeing 737-800' 'engine'\n--make CFM56-7B"]
    U --> Q["build_mro_query()\nConstructs a 12-step Module-Level\nMRO Opportunity Intelligence query:\n• Engine architecture validation\n• Thermal/mechanical stress per module\n• Incident + SDR signal clustering\n• AD/regulatory overlay by module\n• Fleet age + LLP concentration\n• Subcomponent opportunity mapping\n• Competitive landscape per module\n• Module opportunity ranking\n• Strategic investment recommendations"]
    Q --> I["IterativeResearcher.run()\noutput_length='5-8 pages'\noutput_instructions=\n  get_output_instructions()"]
    I --> R["Research Loop\n(iterative, up to max_iterations / max_time)"]
    R --> W["Writer Agent\nProduces 12-section Report\n+ JSON with:\n  module_opportunity_ranking[]\n  subcomponent_exposure_matrix[]"]
    W --> E["extract_json_from_report()\nParses JSON block from output"]
    E --> O1["outputs/*.md\n(Markdown Report)"]
    E --> O2["outputs/*.json\n(Structured JSON)"]
```

---

## Component Diagram

```mermaid
graph TB
    subgraph EntryPoints["📂 Entry Points"]
        EP1["run_mro_research.py\nMRO intelligence report runner"]
        EP2["run_email_pattern_research.py\nEmail pattern researcher"]
        EP3["api.py\nFastAPI REST server\nPOST /research\nGET /research/{id}/status\nGET /research/{id}/report"]
        EP4["deep_researcher/main.py\nCLI entry point\n(deep-researcher command)"]
    end

    subgraph Orchestrators["🔧 Core Orchestrators (deep_researcher/)"]
        O1["IterativeResearcher\niterative_research.py\nSingle-topic research loop\nConversation history tracking"]
        O2["DeepResearcher\ndeep_research.py\nMulti-section research pipeline\nParallel section execution"]
    end

    subgraph Agents["🤖 Agents (deep_researcher/agents/)"]
        A1["Thinking Agent\nthinking_agent.py\nReflects on findings\n→ observations string"]
        A2["Knowledge Gap Agent\nknowledge_gap_agent.py\nFinds outstanding research gaps\n→ KnowledgeGapOutput (Pydantic)"]
        A3["Tool Selector Agent\ntool_selector_agent.py\nChooses which tool agents to run\n→ AgentSelectionPlan (Pydantic)"]
        A4["Writer Agent\nwriter_agent.py\nProduces final report from findings"]
        A5["Planner Agent\nplanner_agent.py\nBuilds report outline (DeepResearcher only)\n→ ReportPlan (Pydantic)"]
        A6["Long Writer Agent\nlong_writer_agent.py\nAssembles multi-section reports"]
        A7["Proofreader Agent\nproofreader_agent.py\nFinal quality pass (DeepResearcher only)"]
    end

    subgraph ToolAgents["🛠️ Tool Agents (deep_researcher/agents/tool_agents/)"]
        TA1["WebSearchAgent\nsearch_agent.py\nPerforms Google SERP searches\nSummarizes top results"]
        TA2["SiteCrawlerAgent\ncrawl_agent.py\nCrawls a specific website\nExtracts detailed content"]
        TA3["[Custom Tool Agents]\nYou can add your own here"]
    end

    subgraph Tools["⚙️ Tools (deep_researcher/tools/)"]
        T1["web_search.py\n@function_tool: web_search()\nSerperClient → Google Search API\nSearchXNGClient → Self-hosted search\nFilter Agent → Relevance ranking\nscrape_urls() → HTML to text via\naiohttp + BeautifulSoup"]
        T2["crawl_website.py\n@function_tool: crawl_website()\ncrawls sitemap or URL list\nextract_links() + fetch pages"]
    end

    subgraph LLMLayer["🧠 LLM Layer (deep_researcher/llm_config.py)"]
        L1["LLMConfig\n• search_provider\n• reasoning_model (KnowledgeGap, ToolSelector)\n• main_model (Writer, Planner)\n• fast_model (WebSearchAgent, Filter)"]
        L2["provider_mapping\nopenai / openrouter / deepseek\ngemini / anthropic / perplexity\nhuggingface / local / azure_openai"]
        L3["OpenAI Agents SDK\n(agents package)\nAgent, Runner, function_tool\nWebSearchTool, tracing"]
    end

    subgraph Search["🔍 Search Integration"]
        S1["Serper API\nhttps://google.serper.dev/search\nX-API-KEY header auth"]
        S2["SearchXNG\nSelf-hosted open-source\nGET /search?q=...&format=json"]
        S3["OpenAI Web Search\nNative WebSearchTool\n(OpenAI models only)"]
    end

    EP1 & EP2 & EP3 & EP4 --> Orchestrators
    O1 --> Agents
    O2 --> O1
    A3 --> ToolAgents
    TA1 --> T1
    TA2 --> T2
    T1 --> Search
    Orchestrators --> LLMLayer
    Agents --> LLMLayer
    ToolAgents --> LLMLayer
```

---

## Component Reference

### Entry Points

| File                            | Purpose                                                                                                                                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `run_mro_research.py`           | CLI script for the Module-Level MRO Opportunity Intelligence Report. Accepts `aircraft`, `part`, `--make`, `--context`, `--max-iterations`, `--max-time`. Outputs `.md` + `.json` to `outputs/`. |
| `run_email_pattern_research.py` | CLI script to research corporate email patterns for a given company.                                                                                                                             |
| `api.py`                        | FastAPI REST server. `POST /research` starts a background research task, `GET /research/{id}/status` polls progress, `GET /research/{id}/report` fetches the output path.                        |
| `deep_researcher/main.py`       | Entrypoint for the `deep-researcher` CLI command installed via `pip`.                                                                                                                            |

---

### Core Orchestrators

#### `IterativeResearcher` (`deep_researcher/iterative_research.py`)

The heart of the system. Manages the research conversation via a `Conversation` object that tracks every iteration's:

- `gap` — the knowledge gap being addressed
- `tool_calls` — which agents were called and with what queries
- `findings` — what those agents returned
- `thought` — the thinking agent's reflection

**Loop constraints:** `max_iterations` (count) AND `max_time_minutes` (wall-clock). Whichever trips first ends the loop.

**Key methods:**

- `run(query, output_length, output_instructions)` — top-level method
- `_generate_observations()` → Thinking Agent
- `_evaluate_gaps()` → Knowledge Gap Agent  
- `_select_agents()` → Tool Selector Agent
- `_execute_tools()` → runs selected tool agents **concurrently** via `asyncio.as_completed()`
- `_create_final_report()` → Writer Agent

#### `DeepResearcher` (`deep_researcher/deep_research.py`)

Wraps `IterativeResearcher` for multi-section reporting:

1. **Planner Agent** → generates a `ReportPlan` (list of sections with key questions)
2. **asyncio.gather** → runs one `IterativeResearcher` per section in parallel
3. **Long Writer / Proofreader** → compiles section drafts into a coherent whole

---

### Agents

All agents are `ResearchAgent` instances (thin wrappers over the SDK's `Agent` class). Each has:

- A **system prompt** (instructions)
- A **model** (chosen from `LLMConfig`)
- An optional **output type** (Pydantic model for structured output) or **output parser** (fallback for models that don't support structured output natively)

| Agent               | Model Used        | Output Type          |
| ------------------- | ----------------- | -------------------- |
| Thinking Agent      | `fast_model`      | Plain string         |
| Knowledge Gap Agent | `reasoning_model` | `KnowledgeGapOutput` |
| Tool Selector Agent | `reasoning_model` | `AgentSelectionPlan` |
| Writer Agent        | `main_model`      | Plain string         |
| Planner Agent       | `reasoning_model` | `ReportPlan`         |
| Long Writer Agent   | `main_model`      | Plain string         |
| Proofreader Agent   | `main_model`      | Plain string         |

---

### Tool Agents

Tool agents are the "hands" of the system — they actually go out and fetch data.

#### `WebSearchAgent` (`search_agent.py`)

- Takes an `AgentTask` (with `query`, `entity_website`, `gap`)
- Optimizes the query to a 3-5 word Google search term
- Calls `web_search()` function tool
- Returns a `ToolAgentOutput` with a 3+ paragraph summary and source URLs

#### `SiteCrawlerAgent` (`crawl_agent.py`)

- Takes an `AgentTask` with a specific website URL
- Crawls the site's pages
- Returns extracted content as a `ToolAgentOutput`

**How the Tool Selector Agent knows about available tool agents:** Their names and descriptions are listed in the Tool Selector Agent's system prompt in `tool_selector_agent.py`. **To add a new tool agent, you must update this prompt.**

---

### Tools (Underlying Integrations)

#### `web_search` (`deep_researcher/tools/web_search.py`)

This is a `@function_tool` — a Python function the SDK exposes to agents as a callable tool.

**Pipeline for each search call:**

1. `SerperClient.search(query)` → POST to `https://google.serper.dev/search` with `X-API-KEY` header → returns organic results (url, title, snippet)
2. `SearchFilterAgent` (a mini LLM call) → filters the list for relevance → returns top 5
3. `scrape_urls()` → concurrently GETs each URL via `aiohttp` with SSL disabled
4. `html_to_text()` → strips HTML with BeautifulSoup, extracts text from `h1-h6, p, li, blockquote`
5. Content trimmed to `CONTENT_LENGTH_LIMIT = 10,000` characters to stay within token limits
6. Returns a list of `ScrapeResult(url, title, description, text)` objects

**Search provider selection (set in `LLMConfig`):**

- `"serper"` → `SerperClient` (Google via Serper.dev REST API)
- `"searchxng"` → `SearchXNGClient` (self-hosted SearXNG instance)
- `"openai"` → native `WebSearchTool()` (only works with OpenAI models)

---

### LLM Configuration

`LLMConfig` (`deep_researcher/llm_config.py`) defines three model roles:

| Role              | Default       | Used By                                                 |
| ----------------- | ------------- | ------------------------------------------------------- |
| `reasoning_model` | `o3-mini`     | Knowledge Gap Agent, Tool Selector Agent, Planner Agent |
| `main_model`      | `gpt-4o`      | Writer Agent, Proofreader, Long Writer                  |
| `fast_model`      | `gpt-4o-mini` | WebSearchAgent, SearchFilterAgent, SiteCrawlerAgent     |

**Supported providers:** `openai`, `deepseek`, `openrouter`, `gemini`, `anthropic`, `perplexity`, `huggingface`, `local` (Ollama/LM Studio), `azure_openai`

All non-OpenAI providers use `OpenAIChatCompletionsModel` with a custom `base_url` — so they all speak the same OpenAI API spec. This is why the code can switch between DeepSeek, Gemini, or a local Ollama model by just changing `.env` variables.

**Structured output fallback:** Not all providers support OpenAI's native structured output (`json_schema` response format). The `model_supports_structured_output()` function checks the provider's base URL. For providers that don't support it, agents use `output_parser` — a Pydantic-based text parser that extracts JSON from the LLM's plain text response.

---

## Search Integration: How Serper Works

```mermaid
sequenceDiagram
    participant A as WebSearchAgent
    participant T as web_search() tool
    participant SC as SerperClient
    participant G as Google (via Serper API)
    participant FA as SearchFilterAgent (LLM)
    participant W as Web Pages (aiohttp)

    A->>T: web_search("CFM56 HPT blade repair")
    T->>SC: search(query)
    SC->>G: POST https://google.serper.dev/search\n{"q": "CFM56 HPT blade repair"}\nX-API-KEY: {SERPER_API_KEY}
    G-->>SC: JSON with organic results\n[{link, title, snippet}, ...]
    SC->>FA: Filter results for relevance (LLM call)
    FA-->>SC: Top 5 relevant results
    SC-->>T: List[WebpageSnippet]
    T->>W: GET each URL concurrently (aiohttp, timeout=8s)
    W-->>T: HTML content
    T->>T: html_to_text() → strip HTML\nextract h1-h6, p, li tags\ntrim to 10,000 chars
    T-->>A: List[ScrapeResult(url, title, desc, text)]
```

**Key point:** Serper is a **plain REST API** — not MCP. You send it an HTTP POST with your search query and `SERPER_API_KEY`, and it returns Google search results as JSON. The SDK doesn't know about Serper at all — it just sees a Python function `web_search()` decorated with `@function_tool`.

---

## How to Extend: Adding a Custom Tool Agent

The system is designed to be extended. Here's the 4-step process:

### Step 1 — Create the tool (`deep_researcher/tools/`)

```python
# deep_researcher/tools/my_custom_tool.py
from agents import function_tool

@function_tool
async def my_tool(query: str) -> str:
    """Call my external API or data source."""
    # ... your HTTP call or logic here ...
    return result_as_string
```

### Step 2 — Create the tool agent (`deep_researcher/agents/tool_agents/`)

```python
# deep_researcher/agents/tool_agents/my_agent.py
from ...tools.my_custom_tool import my_tool
from ..baseclass import ResearchAgent
from . import ToolAgentOutput

INSTRUCTIONS = """You are a specialized research agent...
Only output JSON matching: """ + ToolAgentOutput.model_json_schema()

def init_my_agent(config) -> ResearchAgent:
    return ResearchAgent(
        name="MyCustomAgent",
        instructions=INSTRUCTIONS,
        tools=[my_tool],
        model=config.fast_model,
        output_type=ToolAgentOutput,
    )
```

### Step 3 — Register the agent (`deep_researcher/agents/tool_agents/__init__.py`)

```python
from .my_agent import init_my_agent

def init_tool_agents(config) -> dict:
    return {
        "WebSearchAgent": init_search_agent(config),
        "SiteCrawlerAgent": init_crawl_agent(config),
        "MyCustomAgent": init_my_agent(config),   # ← add here
    }
```

### Step 4 — Tell the Tool Selector Agent (`tool_selector_agent.py`)

Add a line to the `INSTRUCTIONS` string:

```
- MyCustomAgent: Retrieve data from [describe your source] when [describe the use case]
```

The LLM will now autonomously decide to call your agent when the knowledge gap matches.

---

## Data Flow: One Research Iteration

```mermaid
sequenceDiagram
    participant IR as IterativeResearcher
    participant TH as Thinking Agent
    participant KG as Knowledge Gap Agent
    participant TS as Tool Selector Agent
    participant WS as WebSearchAgent
    participant SC as SiteCrawlerAgent
    participant CV as Conversation

    IR->>TH: Current history + query
    TH-->>CV: observations (thought)
    IR->>KG: Current history + query
    KG-->>IR: KnowledgeGapOutput\n(research_complete?, outstanding_gaps[])
    IR->>TS: Next gap + history
    TS-->>IR: AgentSelectionPlan\n(tasks: [{agent, query, entity_website}])
    par Concurrent Tool Execution
        IR->>WS: AgentTask JSON
        WS-->>IR: ToolAgentOutput (summary + sources)
    and
        IR->>SC: AgentTask JSON
        SC-->>IR: ToolAgentOutput (crawled content)
    end
    IR->>CV: append findings to iteration history
    Note over IR: Loop continues until\nresearch_complete=True\nor constraints hit
```

---

## File Structure Reference

```
agents-deep-research/
│
├── run_mro_research.py              # MRO Opportunity Intelligence CLI entry point
├── run_email_pattern_research.py    # Email pattern research CLI entry point
├── api.py                           # FastAPI REST server
│
├── deep_researcher/                 # Core library
│   ├── __init__.py                  # Exports: IterativeResearcher, DeepResearcher, LLMConfig
│   ├── iterative_research.py        # IterativeResearcher + Conversation class
│   ├── deep_research.py             # DeepResearcher (multi-section)
│   ├── llm_config.py                # LLMConfig, provider_mapping, model helpers
│   ├── main.py                      # CLI entry (deep-researcher command)
│   │
│   ├── agents/
│   │   ├── baseclass.py             # ResearchAgent, ResearchRunner (SDK wrappers)
│   │   ├── thinking_agent.py        # Reflection / observations
│   │   ├── knowledge_gap_agent.py   # Gap identification
│   │   ├── tool_selector_agent.py   # AgentTask + AgentSelectionPlan
│   │   ├── writer_agent.py          # Final report writer
│   │   ├── planner_agent.py         # Report outline planner
│   │   ├── long_writer_agent.py     # Multi-section report writer
│   │   ├── proofreader_agent.py     # Final proofreading pass
│   │   │
│   │   ├── tool_agents/
│   │   │   ├── __init__.py          # init_tool_agents() registry
│   │   │   ├── search_agent.py      # WebSearchAgent
│   │   │   └── crawl_agent.py       # SiteCrawlerAgent
│   │   │
│   │   └── utils/
│   │       └── parse_output.py      # Pydantic output parser fallback
│   │
│   ├── tools/
│   │   ├── web_search.py            # web_search() @function_tool + SerperClient
│   │   └── crawl_website.py         # crawl_website() @function_tool
│   │
│   └── utils/
│       └── os.py                    # env var helpers
│
├── prompts/                         # Reference prompt files (not used by runtime)
├── outputs/                         # Generated reports (.md + .json)
├── examples/                        # Usage examples
└── tests/                           # Test suite
```

---

*Generated: 2026-03-02 | Based on full source code analysis of `agents-deep-research`*
