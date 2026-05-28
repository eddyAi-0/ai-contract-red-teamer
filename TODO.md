# TODO

## Next steps

- [ ] Deploy on Streamlit Cloud
- [ ] Add live demo badge to README
- [ ] Pin repository on GitHub profile

## Known limitations

See "Code review notes" section below for technical debt identified during
internal review.

## Code review notes (future improvements)

Technical debt — not blocking, but worth addressing in future iterations:

- [ ] **Citation grounding** — verify that legal excerpts returned by the
  RAG appear verbatim in retrieved chunks. Currently the LLM is trusted to
  cite faithfully; a post-hoc `excerpt in chunk_text` check (with fuzzy
  match) would catch hallucinated citations and improve trust.

- [ ] **Per-finding retrieval** — `analyze_structured_with_rag` currently
  embeds the entire contract as a query. For long contracts the embedding
  becomes diluted. Switch to per-clause or per-finding retrieval for more
  targeted RAG context.

- [ ] **Configurable `top_k`** — currently hardcoded to 3. Expose via env
  var. For long contracts, 3 chunks of legal context may be insufficient.

- [ ] **Underscore imports** — `app.py` imports `_risk_label` and
  `_SEVERITY_ORDER` from `orchestrator/orchestrator.py`. Promote to public
  API or extract to `utils/constants.py`.

- [ ] **Granular error handling** — `app.py` uses generic `except Exception`.
  Distinguish `anthropic.RateLimitError`, `anthropic.AuthenticationError`,
  PDF parsing errors, and network errors for better UX.

- [ ] **JSON schema validation** — agents return dicts validated only by
  retry logic on parse failure. A Pydantic model would catch silent
  semantic errors (missing `findings` or `agent_type`).

- [ ] **Optional parallel agent execution** — `asyncio.gather` with
  `asyncio.Semaphore(3)` would give ~3x speedup. Current sequential design
  is justified by live progress UX, but parallel mode would help non-
  interactive batch use cases.
