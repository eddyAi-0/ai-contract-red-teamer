# AI Contract Red-Teamer

A multi-agent system that analyzes contracts and Terms of Service to surface dangerous clauses, ambiguities, and hidden traps — before you sign.

## 📸 Demo

> Tested on Spotify Terms of Service (Italian PDF) — produces a 7.7/10
> HIGH risk report with 27 findings, citing GDPR Article 13 from
> indexed legal sources.

![Home](screenshots/01_home.png)
*Upload a PDF contract or use the included sample.*

![Analyzing](screenshots/02_analyzing.png)
*Three specialized agents analyze the contract sequentially.*

![Report](screenshots/03_report_overview.png)
*Color-coded risk score with per-agent breakdown.*

![Findings](screenshots/04_findings_list.png)
*All findings filterable by severity and agent type.*

![Finding Detail](screenshots/05_finding_expanded.png)
*Each finding cites relevant GDPR articles from indexed legal sources.*

## Features

- **PDF upload** — drag-and-drop any contract PDF directly in the browser
- **3 specialized AI agents** — Legal, Financial, and Practical each attack the contract from a different angle
- **Live progress UI** — watch each agent complete in real-time with scores
- **Risk score 0–10** — color-coded (green → red) with a MINIMAL/LOW/MEDIUM/HIGH/CRITICAL label
- **RAG-augmented analysis** — findings are cross-referenced against the GDPR text (EU Reg. 2016/679)
- **Filterable findings** — filter by severity (Critical/High/Medium/Low) and agent type
- **Download report** — export as Markdown or raw JSON

## Quick Start

```bash
# 1. Clone & virtual environment
git clone https://github.com/eddyAi-0/ai-contract-red-teamer.git
cd ai-contract-red-teamer
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API keys
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY (required) and VOYAGE_API_KEY (for RAG)

# 4. (Optional) Index GDPR reference document for RAG citations
python -m rag.indexer

# 5. Launch the app
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Architecture

Three specialized agents attack the same contract from different angles, then an Orchestrator synthesizes their findings into a final risk report.

```
PDF / Text Input
      │
      ▼
┌─────────────────────────────────────────┐
│              Orchestrator               │
│  coordinates agents, computes risk score│
└────────┬──────────┬──────────┬──────────┘
         │          │          │
    ┌────▼───┐ ┌────▼───┐ ┌───▼────┐
    │ Legal  │ │Finance │ │Practic.│
    │ Agent  │ │ Agent  │ │ Agent  │
    └────────┘ └────────┘ └────────┘
         │          │          │
         └──────────┴──────────┘
                    │
              Final Report
           (risk score 0-100)
```

### Agents

| Agent | Focus |
|-------|-------|
| **Legal Agent** | Ambiguous clauses, GDPR violations, unilateral terms, jurisdiction traps |
| **Financial Agent** | Hidden costs, penalties, auto-renewals, payment conditions |
| **Practical Agent** | Unrealistic obligations, impossible deadlines, missing exit clauses |

### Risk Score Weights

| Agent | Weight |
|-------|--------|
| Legal | 40% |
| Financial | 35% |
| Practical | 25% |

## Tech Stack

- **Python 3.11+**
- **Anthropic API** (`claude-sonnet-4-5`) — direct calls, no LangChain
- **Streamlit** — frontend with live progress UI
- **pdfplumber** — PDF text extraction
- **ChromaDB** — RAG vector store
- **Voyage AI** — embeddings for semantic search
- **python-dotenv** — environment variable management

## Project Structure

```
ai-contract-red-teamer/
├── agents/
│   ├── base_agent.py          # BaseAgent: Anthropic API call + JSON retry
│   ├── legal_agent.py         # Legal risk analysis
│   ├── financial_agent.py     # Financial risk analysis
│   └── practical_agent.py     # Practical risk analysis
├── orchestrator/
│   └── orchestrator.py        # Coordinates agents, weighted score, executive summary
├── rag/
│   ├── vectorstore.py         # ChromaDB + Voyage AI integration
│   ├── indexer.py             # Index PDFs from rag/documents/
│   └── documents/             # Reference legal documents (GDPR PDF)
├── ui/
│   ├── styles.py              # CSS injection and color helpers
│   └── report_renderer.py     # Streamlit report rendering logic
├── utils/
│   └── pdf_parser.py          # PDF text extraction with pdfplumber
├── tests/
│   └── test_agents.py         # Unit tests
├── screenshots/               # App screenshots
├── app.py                     # Streamlit entry point
├── test_end_to_end.py         # CLI end-to-end test
├── .env.example
├── requirements.txt
└── README.md
```

## Screenshots

_Screenshots will be added after first run._

## Roadmap

- [x] Step 1 — Project setup, BaseAgent, PDF parser
- [x] Step 2 — Legal, Financial, Practical agents + Orchestrator + RAG
- [x] Step 3 — Streamlit frontend with live progress and filterable report
- [ ] Step 4 — Deploy on Streamlit Cloud
