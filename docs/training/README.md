# Training plan — Toni & Sheriff (local AI agents + hybrid RAG)

A hands-on curriculum that teaches the concepts behind this project by building on
and extending its real code. Every module ends with a **checkpoint** (a short concept
quiz plus a practical task with pass/fail criteria) so progress is measurable.

## Who this is for

Software engineers with an **embedded/systems background** and **basic Python**. You are
comfortable with C, state machines, interfaces (HALs), memory/timing constraints, and
debugging at the boundary — but may be new to the Python AI/data ecosystem and to
*probabilistic* systems. Each module opens with a short **"From embedded to here"** bridge
that maps a new idea onto something you already know.

## The one mindset shift

Embedded systems are **deterministic**: same input → same output, and you design for worst
case. LLMs are **probabilistic**: the same prompt can yield different text, latency varies
by seconds, and "correctness" is a distribution, not a guarantee. Most of the engineering in
this project exists to put *deterministic scaffolding* (validation, retrieval, a debate,
explicit human approval, security checks) around a non-deterministic core. Keep that framing
and the whole codebase makes sense.

## Prerequisites (Module 0 — do this first)

1. Work through the root [README](../../README.md) "Setup" section: install deps, start
   services, init the DB.
2. Bring the system up and confirm all four components are green:
   ```bash
   ./run.sh start
   ./run.sh status
   ```
3. Open the app at http://localhost:8501, run one debate end to end, and click
   **Save to knowledge base** once. You now have a working reference system to study.
4. Skim the project layout in the root README so the file names below are familiar.

**Checkpoint 0 (gate):** `./run.sh status` shows colima, Postgres, Ollama, and the app all
running, and `python -m scripts.init_db` prints a non-error schema summary. If not, fix the
environment before continuing — every later lab depends on it.

## Sequence and why it's ordered this way

The order goes **foundations → data → retrieval → agents → product → hardening**, so each
module only depends on earlier ones. Don't skip ahead: Module 5 (RAG) won't make sense
without 3 (embeddings) and 4 (vector storage).

| # | Module | You'll be able to… | Est. time |
|---|--------|--------------------|-----------|
| 1 | [Python patterns used here](module-01-python-patterns.md) | Read the codebase: dataclasses, type hints, ABCs, generators/streaming, context managers | 2–3 h |
| 2 | [LLMs & the provider abstraction](module-02-llm-and-providers.md) | Explain tokens/inference/prompting; swap local↔cloud behind one interface | 3–4 h |
| 3 | [Embeddings & semantic search](module-03-embeddings.md) | Turn text into vectors and rank by cosine similarity | 2–3 h |
| 4 | [Vectors in Postgres (pgvector + SQL)](module-04-pgvector-and-sql.md) | Store/query vectors and full-text in one DB; reason about indexes | 3–4 h |
| 5 | [RAG & hybrid retrieval (RRF)](module-05-rag-hybrid-retrieval.md) | Build chunk→embed→retrieve; fuse dense+sparse with RRF; rerank | 4–5 h |
| 6 | [Multi-agent orchestration](module-06-multi-agent-orchestration.md) | Model the Toni/Sheriff debate as a state machine to a decision | 3–4 h |
| 7 | [App & lifecycle](module-07-app-and-lifecycle.md) | Understand Streamlit's reactive model; Docker/compose; the run.sh lifecycle | 3 h |
| 8 | [Security & robustness](module-08-security.md) | Defend an ingestion path (SSRF, limits, secrets) | 2–3 h |
| 9 | [Capstone](module-09-capstone.md) | Extend the system and prove it with tests | 5–8 h |
| — | [Final assessment](final-assessment.md) | Demonstrate end-to-end understanding | 2 h |

Suggested cadence: **~3 weeks part-time** (3 modules/week) or a **5-day intensive**
(Modules 1–2 / 3–4 / 5 / 6–7 / 8–9). Total ≈ 30–40 hours including the capstone.

## How the control points work

- **Concept check** — short questions; answers are in a `<details>` block so you can
  self-grade. Aim for 80%+ before moving on.
- **Practical task** — a change or script you run against the real system, with an explicit
  *pass criterion* (an observable output). This is the real gate.
- **Capstone + final assessment** — graded against the rubric in
  [final-assessment.md](final-assessment.md).

## How to use the labs safely

- Do exercises on a branch: `git checkout -b training/<your-name>`.
- Labs that write to the knowledge base use a throwaway prefix or clean up after themselves;
  each lab says so. To reset the KB entirely:
  ```bash
  docker exec local-pgvector psql -U agent_user -d agent_db -c "TRUNCATE knowledge_chunks RESTART IDENTITY;"
  ```
- Keep the app running in one terminal (`./run.sh logs` to watch it) and run lab scripts in
  another with `.venv/bin/python`.

## Instructor notes

- Each module is self-contained and references exact source files, so it doubles as
  onboarding documentation.
- The checkpoints are designed to be **observable** (a number, a passing test, a visible UI
  state) rather than essay-graded — suitable for async cohorts.
- If you run this as a cohort, the capstone PRs make a natural review/discussion artifact.
