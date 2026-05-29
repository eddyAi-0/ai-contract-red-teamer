# ⚖️ AI Contract Red-Teamer

> Agentic AI system that analyzes PDF contracts for risky clauses. Three specialized agents
> (Legal, Financial, Practical) reason in **tool-use loops** — deciding when to query a RAG corpus
> of GDPR legislation and verifying every citation against it — and a fourth **critic agent**
> reviews the merged findings and discards any whose citations cannot be verified, guarding against
> hallucinated legal references.

[![Tests](https://img.shields.io/badge/tests-69%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://python.org)

---

## Demo

> Tested on real Spotify Terms of Service (Italian PDF, 273 KB). A full agentic run (three agents in
> tool-use loops + the citation critic) produces a **~TODO/10 TODO** risk report with **TODO findings**,
> citing GDPR articles from indexed legal sources.
>
> _Performance (to be measured on a real run): **~$TODO per run**, **~TODO sec per run**. These shift
> from the previous single-pass numbers because each agent now makes multiple API calls inside its loop
> and the critic adds a verification pass._

### Upload
![Home](screenshots/01_home.png)
*Upload a PDF contract or use the included sample.*

### Live analysis
![Analyzing](screenshots/02_analyzing.png)
*Three specialized agents analyze the contract in sequence, each running its own tool-use loop, with live progress updates.*

### Risk report
![Report Overview](screenshots/03_report_overview.png)
*Color-coded risk score (0–10) with per-agent breakdown and executive summary.*

### Findings list
![Findings](screenshots/04_findings_list.png)
*All findings filterable by severity (Critical / High / Medium / Low) and agent type, sorted by severity.*

### Detailed finding with GDPR citations
![Finding Detail](screenshots/05_finding_expanded.png)
*Each finding includes the problematic clause (cited verbatim in source language), an actionable
recommendation, and verbatim citations from indexed legal sources via RAG
(here: GDPR Article 13 on transparency requirements).*

---

## Features

- **Agentic analysis** — three specialized agents reason in tool-use loops, deciding when to query the legal corpus rather than doing a single fixed pass
- **Citation verification** — a critic agent verifies every legal citation against the corpus and discards hallucinated ones
- **RAG-augmented** — cites real GDPR articles from 547 indexed chunks (EU Reg. 2016/679, EN)
- **Multilingual support** — handles contracts in any language; UI and analysis output always in English; original clauses cited verbatim
- **Weighted risk scoring** — Legal 40%, Financial 35%, Practical 25%
- **Filterable findings** — by severity and agent type, ordered by risk
- **Downloadable reports** — Markdown or JSON
- **Production-ready** — Docker support, 69 unit tests, container healthchecks

## Tech Stack

The backend is Python 3.11. LLM reasoning runs on the Anthropic API (`claude-sonnet-4-5-20250929`, a
pinned dated version for reproducibility) with direct API calls — no framework wrapper. Agents use the
native tool-use loop to call `search_legal_corpus` and `verify_citation` on demand. Embeddings are
generated via Voyage AI (`voyage-3`) and stored in ChromaDB. The frontend is Streamlit. PDF extraction
uses pdfplumber with a configurable character limit to handle both short contracts and long legal
documents. The test suite has 69 tests written with pytest, using fully mocked Anthropic and Voyage AI
clients (zero API cost to run).

## Quick Start

```bash
# 1. Clone and create a virtual environment
git clone https://github.com/eddyAi-0/ai-contract-red-teamer.git
cd ai-contract-red-teamer
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API keys
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY (required) and VOYAGE_API_KEY (for RAG)

# 4. Index the GDPR reference document (one-time, ~2 minutes)
python -m rag.indexer

# 5. Run
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## 🐳 Docker

Run the entire stack with a single command:

```bash
cp .env.example .env
# Add ANTHROPIC_API_KEY and VOYAGE_API_KEY to .env

docker-compose up --build
```

Open [http://localhost:8501](http://localhost:8501)

The GDPR vector store is persisted in a named Docker volume — the first run takes ~2 minutes to index;
subsequent runs start instantly.

## Architecture

Three specialized agents analyze the same contract from different angles. Each runs an agentic
tool-use loop: it decides when to query the legal corpus (`search_legal_corpus`) and verifies any
quote it intends to cite (`verify_citation`) before including it. The Orchestrator merges their
findings, then a **critic agent** re-checks every citation and drops the unverifiable ones, before
the final weighted risk score is computed.

```
PDF / Text Input
      │
      ▼
┌──────────────────────────────────────────────┐
│                 Orchestrator                  │
│   runs agents, runs critic, computes score    │
└───┬───────────┬───────────┬───────────────────┘
    │           │           │
┌───▼────┐ ┌────▼───┐ ┌─────▼────┐        ┌──────────────┐
│ Legal  │ │Finance │ │ Practical│  ◄───► │ Legal corpus │
│ Agent  │ │ Agent  │ │  Agent   │  tool  │  (ChromaDB)  │
└───┬────┘ └────┬───┘ └─────┬────┘  loop   └──────▲───────┘
    │           │           │                     │
    └───────────┴───────────┘                     │
                │  merged findings                 │
                ▼                                  │
        ┌───────────────┐   verify_citation /      │
        │ Critic Agent  │ ──── search_legal_corpus ─┘
        │ (verifies &   │
        │  prunes cites)│
        └───────┬───────┘
                │  verified findings
                ▼
          Final Report
        (risk score 0–10)
```

Each `Agent ◄──► Legal corpus` arrow is a loop: the model can search and verify repeatedly within a
single analysis (capped by `max_turns`) before emitting its final JSON.

| Agent | Focus areas |
|---|---|
| **Legal** | Ambiguous clauses, GDPR violations, unilateral modification rights, jurisdiction traps, disproportionate liability caps |
| **Financial** | Hidden costs, disproportionate penalties, auto-renewals, unfavorable payment conditions |
| **Practical** | Unrealistic obligations, impossible deadlines, missing exit clauses, vague compliance requirements |

| Agent | Score weight |
|---|---|
| Legal | 40% |
| Financial | 35% |
| Practical | 25% |

## Notable engineering decisions

**RAG indexing vs. contract truncation.** `extract_text_from_pdf` accepts an optional `max_chars`
parameter (default: 25 000) to protect the LLM context window when analyzing user-uploaded contracts.
The indexer calls the same function with `max_chars=None` to load the full 88-page GDPR document.
Without this distinction, the English GDPR PDF was silently truncated to ~7 pages, yielding 38 chunks
instead of 547 — a 14× reduction in RAG coverage discovered only by comparing chunk counts.

**Agentic tool-use loop, not a single pass.** Each agent runs `analyze_agentic()`: the model is given
the contract plus two tools (`search_legal_corpus`, `verify_citation`) and loops — while the API returns
`stop_reason == "tool_use"`, the tool is executed and its result fed back — until the model emits its
final findings JSON or a `max_turns` cap is hit. This lets the agent decide *what* to look up and *when*,
issuing targeted corpus queries instead of one blind retrieval over the entire contract. The loop is
bounded by `max_turns` and falls back to the single-pass `analyze_structured_with_rag` if it exhausts
its turns, so a misbehaving model can never hang the request. The three agents still run one after the
other at the Orchestrator level — keeping the live progress UI clear and avoiding parallel requests that
would saturate a single API key.

**Citation verification against the corpus (anti-hallucination).** The strongest guarantee of the
system: an LLM asked for legal citations will happily invent plausible-looking article numbers and
quotes. `verify_citation(excerpt)` checks each proposed quote against the actual indexed corpus before
it is allowed into a finding. The match is two-stage against each retrieved chunk (whitespace/case
normalised): an exact-substring fast-path, then a fuzzy stage that slides a window the same word-length
as the excerpt across the chunk and keeps the best `SequenceMatcher` ratio (threshold 0.85). Comparing
against same-length windows — rather than the whole chunk — is what makes the fuzzy stage meaningful: a
short quote scored against an 800-character chunk would always fall near zero and never clear the
threshold. The agents call this before citing, and the **critic agent** runs a second verification pass
over the merged findings, discarding any finding whose citations are all unverifiable and unsupported.

**A dedicated critic agent.** Rather than trusting each agent to police its own citations, a separate
`CriticAgent` (same tool-use loop, different system prompt) reviews the merged findings list as a whole.
Separation of concerns: the specialist agents optimize for *finding* risks, the critic optimizes for
*rejecting* unfounded ones. The critic pass is skipped when no vectorstore is attached — with no corpus
to verify against, every citation would be rejected and the pass would be purely destructive.

**Stale cache recovery.** Streamlit's `@st.cache_resource` keeps the VectorStore object alive across
page reloads. If `rag/chroma_db/` is deleted and rebuilt while the server is running, the cached object
holds a reference to a now-deleted ChromaDB collection UUID. A `_safe_vectorstore()` wrapper probes the
collection on every call; on failure it clears the Streamlit cache and re-initializes transparently,
preventing the "Collection does not exist" crash without requiring a server restart.

**JSON parsing hardening.** The Anthropic API occasionally returns control characters (U+0000–U+001F,
excluding `\n`, `\t`, `\r`) inside JSON strings extracted from contract text. These silently break
`json.loads`. A `re.sub` pass runs before every parse attempt. `max_tokens` is raised to 8 192 only
for the structured-output methods, leaving the free-text `analyze()` path unchanged.

## Architecture: next steps

The following is a planned evolution, **not yet implemented**, documented here to show the intended
direction.

**Conditional re-dispatch orchestrator.** Today the Orchestrator runs each agent exactly once, then
critiques. The next step is to make the Orchestrator itself reason over the returned findings and decide
whether a follow-up pass is worthwhile — for example, re-dispatching the Legal agent with a targeted
question ("the liability cap looks disproportionate; check it against the indemnification clause in
§8") when an initial finding is high-severity but thinly supported, or when two agents surface
overlapping issues that need reconciliation. To keep cost and latency bounded, re-dispatch would be
governed by an explicit cap (e.g. at most one extra pass per agent, or a global budget of N additional
turns), so the system can deepen its analysis where it matters without unbounded looping. This turns the
Orchestrator from a fixed pipeline into a genuine planner.

## Multilingual handling

The system is designed to handle contracts in any language. Agent system prompts explicitly instruct
the model to quote contract clauses verbatim (preserving the original language) while writing titles,
descriptions, recommendations, and summaries in English. This makes the output consistent regardless
of whether the input is Italian, German, French, or English.

## Testing

```bash
python -m pytest tests/ -v
```

69 tests cover the agent layer (including the agentic loop, `verify_citation`, and the critic), the
Orchestrator, the RAG pipeline, and the vector store — all with mocked Anthropic and Voyage AI clients.
The loop tests mock *sequences* of API responses (a `tool_use` turn followed by a final turn), so the
multi-turn behavior is exercised end-to-end without any real API calls or cost.

## Project structure

```
ai-contract-red-teamer/
├── agents/
│   ├── base_agent.py          # API call, agentic tool-use loop, verify_citation, JSON cleanup
│   ├── legal_agent.py
│   ├── financial_agent.py
│   ├── practical_agent.py
│   └── critic_agent.py        # Reviews merged findings, prunes unverifiable citations
├── orchestrator/
│   └── orchestrator.py        # Runs agentic agents, critic pass, weighted scoring, executive summary
├── rag/
│   ├── vectorstore.py         # ChromaDB + Voyage AI, stale-cache recovery
│   ├── indexer.py             # Indexes PDFs from rag/documents/ with no char limit
│   └── documents/             # GDPR EN (EU Reg. 2016/679) — 547 chunks
├── ui/
│   ├── styles.py              # CSS injection and color helpers
│   └── report_renderer.py     # Streamlit report rendering and Markdown export
├── utils/
│   └── pdf_parser.py          # PDF extraction, configurable max_chars, truncation marker
├── tests/                     # 69 unit tests
├── screenshots/
├── app.py                     # Streamlit entry point and state machine
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Roadmap

- [x] Step 1 — Project setup, BaseAgent, PDF parser
- [x] Step 2 — Legal, Financial, Practical agents + Orchestrator + RAG
- [x] Step 3 — Streamlit frontend with live progress and filterable report
- [x] Step 4 — Docker support for one-command deployment
- [x] Step 5 — Agentic refactor: tool-use loops + citation-verifying critic agent
- [ ] Step 6 — Conditional re-dispatch orchestrator (see *Architecture: next steps*)
- [ ] Step 7 — Deploy on Streamlit Cloud
- [ ] Step 8 — Additional legal sources (German BGB, US consumer law)
- [ ] Step 9 — Multi-document comparison

## License

MIT
