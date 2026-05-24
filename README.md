# AI Contract Red-Teamer

A multi-agent system that analyzes contracts and Terms of Service to surface dangerous clauses, ambiguities, and hidden traps — before you sign.

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

## Tech Stack

- **Python 3.11+**
- **Anthropic API** (`claude-sonnet-4-5`) — direct calls, no LangChain
- **pdfplumber** — PDF text extraction
- **Streamlit** — frontend (coming in Step 3)
- **ChromaDB** — RAG vector store (coming in Step 2)
- **python-dotenv** — environment variable management

## Setup

### 1. Clone & create virtual environment

```bash
git clone https://github.com/eddyAi-0/ai-contract-red-teamer.git
cd ai-contract-red-teamer
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 4. Run (Streamlit frontend — coming soon)

```bash
streamlit run app.py
```

## Project Structure

```
ai-contract-red-teamer/
├── agents/
│   ├── base_agent.py          # BaseAgent class with Anthropic API call
│   ├── legal_agent.py         # Legal risk analysis (Step 2)
│   ├── financial_agent.py     # Financial risk analysis (Step 2)
│   └── practical_agent.py     # Practical risk analysis (Step 2)
├── orchestrator/
│   └── orchestrator.py        # Coordinates agents, produces report (Step 2)
├── rag/
│   ├── vectorstore.py         # ChromaDB integration (Step 2)
│   └── documents/             # Reference legal documents for RAG
├── utils/
│   └── pdf_parser.py          # PDF text extraction with pdfplumber
├── tests/
│   └── test_agents.py         # Unit tests
├── app.py                     # Streamlit entry point (Step 3)
├── .env.example
├── requirements.txt
└── README.md
```

## Roadmap

- [x] Step 1 — Project setup, BaseAgent, PDF parser
- [ ] Step 2 — Legal, Financial, Practical agents + Orchestrator + RAG
- [ ] Step 3 — Streamlit frontend
