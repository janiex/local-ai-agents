# Module 9 — Capstone

**Goal:** prove you can extend the system end to end, touching the layers you've learned, and
back it with automated tests. Pick **one** track (each exercises most modules). Budget 5–8 h.

Work on a branch: `git checkout -b training/capstone-<your-name>`.

## Track A — Add a third LLM provider (Modules 1, 2, 6)
Add an OpenAI-compatible or a second local provider behind the existing interface.
- New `src/llm/<name>_provider.py` implementing `LLMProvider.stream` + `health_check`.
- Register it in [factory.py](../../src/llm/factory.py) and `AVAILABLE`.
- Expose it in the sidebar selector ([app.py](../../app.py)).
**Acceptance:** `get_provider("<name>")` drives a full debate via the controller (Module 6
lab) with no changes to `orchestrator.py`. A unit test mocks the HTTP/SDK layer and asserts
`stream()` yields chunks and `complete()` joins them.

## Track B — Add a new retrieval channel or reranker (Modules 3, 4, 5)
Either add a third channel (e.g., a title/metadata boost) fused into RRF, or swap the sparse
channel to a true BM25 (e.g., `pg_search`/ParadeDB) behind `store.sparse_search`.
- Keep the `{id, content, metadata, score}` row contract.
- Fuse via the existing `_reciprocal_rank_fusion` (add your ranked list to the input).
**Acceptance:** a test seeds a known corpus and asserts that a query which *only* your new
channel can satisfy now appears in `hybrid_search` results, while existing queries still rank
correctly. Document the latency impact.

## Track C — Add a CLI front-end (Modules 2, 5, 6, 7)
Build `cli.py` that runs a debate headlessly: takes a request, prints Toni/Sheriff/consolidated
turns, and asks before saving (mirroring the explicit-save rule).
- Reuse `DebateController` and `KnowledgeBase` directly — **no Streamlit import**.
- Support `--provider`, `--rounds`, and a `--no-save` flag.
**Acceptance:** `python cli.py "your request" --rounds 1` completes a debate and only writes to
the KB when the user confirms. A test runs it with a mock provider and asserts no DB write
occurs without confirmation.

## Required for every track: a test suite

Create `tests/` with pytest. Install: `.venv/bin/pip install pytest`. Minimum bar:

```python
# tests/test_fusion.py — pure logic, no services needed
from src.rag.retriever import _reciprocal_rank_fusion

def test_rrf_rewards_agreement():
    a = [{"id": 1}, {"id": 2}, {"id": 3}]   # channel 1 ranking
    b = [{"id": 3}, {"id": 1}, {"id": 9}]   # channel 2 ranking
    fused = _reciprocal_rank_fusion([a, b], k=60)
    ids = [r["id"] for r in fused]
    # id 1 (high in both) should beat id 2 (only in one)
    assert ids.index(1) < ids.index(2)

def test_verdict_parsing():
    from src.agents.orchestrator import DebateController
    assert DebateController._parse_verdict("...\nVERDICT: APPROVE") == "APPROVE"
    assert DebateController._parse_verdict("no verdict here") == "REVISE"  # safe default
```

Run: `.venv/bin/pytest -q`.

Add at least:
- one **pure-logic** test (fusion, verdict parsing, chunking, or URL validation — no services),
- one **integration** test for your track (may require Postgres up; mark it so it can be
  skipped without services),
- a **security** test if your track touches ingestion (reuse Module 8's block list).

## Deliverable

A branch + PR containing your feature, the tests (green), and a short `CAPSTONE.md` describing:
what you built, which alternatives you rejected and why, and one maintenance pitfall you'd warn
the next engineer about. This maps directly onto the [final assessment](final-assessment.md)
rubric.
