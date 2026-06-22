# Final assessment

Two parts: a written check (concepts) and a practical check (the capstone). Pass mark: **70%
written** and a **working capstone** meeting its acceptance criteria.

## Part A — Written (50 points)

Answer in your own words. Point values in brackets.

1. [5] Explain the deterministic-vs-probabilistic mindset shift and name two pieces of
   "deterministic scaffolding" this project wraps around the LLM.
2. [5] An LLM API is stateless. What are the consequences for (a) the orchestrator and (b)
   cost/latency as a debate grows?
3. [5] Dense vs sparse retrieval: give a query each one wins, and say why.
4. [5] Why does RRF fuse on rank rather than raw score? What does `k` control?
5. [5] Why must query and document embeddings come from the same model?
6. [5] Walk through the `DebateController` states and the guard that ends the loop. Why does
   the verdict parser default to `REVISE`?
7. [5] Why does `tsv` use a `GENERATED` column, and why are vectors passed as `'[...]'::vector`?
8. [5] Describe three independent SSRF defences in `url_ingest.py` and the residual risk.
9. [5] Why is the debate engine free of Streamlit imports, and what does that enable?
10. [5] In Streamlit's reactive model, why must debate state live in `session_state`, and what
    does `@st.cache_resource` save?

<details><summary>Grading key (summary points)</summary>

1. Same input → varying output/latency; scaffolding e.g. retrieval, the critic step, explicit
   save, URL security checks, bounded rounds.
2. (a) Full transcript resent each turn (transcript is the memory). (b) Tokens grow with the
   transcript, so cost/latency rise per round.
3. Dense wins on paraphrase/concept; sparse wins on exact identifiers (codes/versions).
4. Cosine and ts_rank scales are incomparable; ranks aren't. Lower `k` sharpens emphasis on
   top ranks.
5. Different models → different vector spaces → meaningless distances.
6. new→toni→sheriff→(toni|done)→consolidate; guard = APPROVE or max_rounds; default REVISE
   avoids false approval on malformed output.
7. GENERATED keeps `tsv` derived/in-sync automatically; the text literal casts correctly
   where a Python list would become a SQL array.
8. Any three of: scheme allowlist, no-credentials, public-IP check, per-hop redirect
   validation, size/timeout caps, content-type allowlist, host allowlist. Residual: DNS
   rebinding.
9. Reusability: same engine for Streamlit/CLI/WhatsApp/tests; testable headlessly.
10. Script re-runs each interaction; only `session_state` persists. `cache_resource` avoids
    reconnecting Postgres / reloading the embedder each run.
</details>

## Part B — Practical (capstone, pass/fail on the rubric)

| Criterion | Weight | Pass bar |
|---|---|---|
| Correctness | 30% | Feature works end to end against the running system |
| Reuse / layering | 20% | Extends through the right seam (interface/facade); no copy-paste of core logic; engine stays UI-agnostic |
| Tests | 25% | ≥1 pure-logic + ≥1 integration (skippable w/o services) + security test if ingestion touched; all green |
| Security & robustness | 15% | Inputs validated at boundaries; no secrets logged/committed; bounded resources |
| Communication | 10% | `CAPSTONE.md` explains design, rejected alternatives, and one maintenance pitfall |

## What "done" looks like
- `.venv/bin/pytest -q` is green.
- Your feature is demonstrable in the app or via the controller API.
- Your PR description states the trade-off you made and the residual risk you accept — the
  same honesty the project applies to DNS rebinding.

## Where to go next (beyond this course)
- Persistence/eviction for sessions; observability (token/latency metrics per turn).
- True BM25 (ParadeDB) and IP-pinning for the fetcher.
- A second front-end (CLI or the WhatsApp design in the docs) to exercise the UI-agnostic core.
