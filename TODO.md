# TODO

## 🌅 Tomorrow (May 29)

- [ ] Verify final GitHub push went through
- [ ] Visit repo in incognito mode to see how a recruiter would see it
- [ ] Deploy on Streamlit Cloud (https://share.streamlit.io)
- [ ] Update README with live demo link once deployed
- [ ] Pin repo on GitHub profile

## 📅 This week

- [ ] (Optional) Add Dockerfile for local containerized deployment
- [ ] (Optional) Write LinkedIn post about the project
- [ ] Start planning Project 3: AI Agent with tool use
  - Decide between Travel Planner or Medical Literature Research Agent
  - Set up new repo and project structure

## 📆 Next 2 weeks

- [ ] Complete Project 3 (estimated: 2 weeks, ~25 hours)
- [ ] Enroll in UniTo Master's in AI for Biomedicine (deadline check)
- [ ] Start learning German (Duolingo, 15 min/day)
- [ ] Improve English to documented B2/C1 level

## 🎯 Medium-term (Summer 2026)

- [ ] Project 4: LLM Evals Framework
- [ ] Polish quiz-oss README and pin it on GitHub
- [ ] Build personal portfolio website (optional)

## 🌍 Long-term (2026-2028)

- [ ] Master's degree at UniTo (2 years, in English)
- [ ] Summer internship in Germany/Austria (DKFZ, EMBL, BioNTech, etc.)
- [ ] Master thesis abroad (ideally Germany/Austria)
- [ ] First job as AI Engineer in Germany/Austria

## 🐛 Known issues / nice-to-haves for AI Contract Red-Teamer

- [ ] Improve error messages for cache invalidation (currently mentions API keys)
- [ ] Add support for additional legal sources (German BGB, US Consumer Code)
- [ ] PDF export of reports (currently only Markdown and JSON)
- [ ] Multi-document analysis (compare two contracts)
- [ ] Cache analyzed contracts to avoid re-running on the same file

## 💡 Notes to self

- The "AI does everything" anxiety is normal but not rational.
  The decisions made tonight (architecture, debugging, measuring) are MINE,
  not the AI's.
- The "fuoricorso" on the bachelor's degree is not a problem in tech,
  especially abroad.
- Real engineers MEASURE, they don't GUESS. Tonight's silent bug (38 vs 547
  chunks) is proof of that mindset.
- Sleep matters more than one more commit.

## 🔧 Code review notes (future improvements)

Technical debt identified during review — not blocking, but worth addressing:

- [ ] **Underscore imports code smell** — `app.py` imports `_risk_label` and
  `_SEVERITY_ORDER` from `orchestrator/orchestrator.py`. Either promote them
  to public API (rename without underscore) or extract them to
  `utils/constants.py` for cleaner separation.

- [ ] **Catch-all error handling** — `app.py` uses generic `except Exception`
  in the analysis flow. Distinguish between `anthropic.RateLimitError`,
  `anthropic.AuthenticationError`, PDF parsing errors, and network errors for
  better UX (currently all errors suggest checking API keys).

- [ ] **JSON schema validation** — agents return dicts validated only by
  retry logic on parse failure. A Pydantic model would catch silent semantic
  errors (e.g., missing `findings` array or `agent_type` field).

- [ ] **Hardcoded `top_k=3` for RAG** — make it configurable via env var or
  config file. For long contracts with many clauses, 3 chunks of legal
  context may be insufficient.

- [ ] **Sequential agent execution** — `asyncio.gather` with `asyncio.Semaphore(3)`
  would give ~3x speedup without saturating the API rate limit. Current
  sequential design is justified by live progress UX, but worth noting as
  alternative architecture for non-interactive batch use cases.
