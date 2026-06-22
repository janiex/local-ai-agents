# Module 5 — RAG and hybrid retrieval (the heart of the project)

**Goal:** build the full pipeline — chunk → embed → store → retrieve — and fuse dense + sparse
results with Reciprocal Rank Fusion, then optionally rerank.

**From embedded to here:** RAG is **giving the processor a working set before it computes** —
like a DMA prefetch of the relevant data into a scratchpad so the expensive unit (the LLM)
operates on exactly what it needs. Hybrid retrieval is **sensor fusion**: two imperfect
sensors (semantic + lexical) combined produce a more robust estimate than either alone.

Reference: the InfoQ article this implements —
<https://www.infoq.com/articles/vector-search-hybrid-retrieval-rag/>.

## Concepts

### 1. Why RAG at all
LLMs are frozen and stateless. RAG injects fresh, specific knowledge into the prompt at
query time instead of retraining. In this project the knowledge is *accumulated solutions* —
retrieved at the start of a task, fed to the agents as context.

### 2. Chunking
[src/rag/chunking.py](../../src/rag/chunking.py) splits text into ~1200-char chunks with
~150-char overlap. Why: embeddings have an input limit and lose precision on huge texts;
overlap prevents a fact from being split across a boundary and lost. (Trade-off: too small =
fragmented context; too large = fuzzy vectors. 1200/150 is a reasonable default.)

### 3. The two channels, recap
- **Dense** finds *conceptually* similar text (Module 3) — strong on paraphrase, weak on
  exact identifiers.
- **Sparse/BM25** finds *lexically* matching text (Module 4) — strong on exact tokens
  (versions, error codes, names), weak on synonyms.
They fail in *opposite* directions, which is exactly why fusing them helps.

### 4. Reciprocal Rank Fusion (RRF)
[src/rag/retriever.py](../../src/rag/retriever.py) `_reciprocal_rank_fusion`:
`score(d) = Σ_channels 1 / (k + rank_d)` with **k = 60**. Key properties:
- It uses **rank position**, not raw scores — so it sidesteps the incompatible score scales
  of cosine vs ts_rank (you can't just add them).
- A document near the top in *either* channel gets a strong contribution; one near the top in
  *both* wins. Lower `k` sharpens the emphasis on top ranks (favoring exact matches).

### 5. Optional cross-encoder reranking
When enabled, [src/rag/embeddings.py](../../src/rag/embeddings.py) `rerank()` scores
(query, passage) pairs with a cross-encoder and reorders the fused top candidates. More
accurate (it reads query+passage *together*) but slower — a precision stage you pay for only
when you turn it on.

### 6. The facade
[src/rag/knowledge.py](../../src/rag/knowledge.py) `KnowledgeBase` ties it together:
`retrieve()` (used at task start) and `add_document()`/`accumulate_solution()` (used on
explicit save). The orchestrator only ever talks to this facade.

## Hands-on lab

1. **Seed a tiny corpus** (cleans up at the end):
   ```python
   from src.rag.knowledge import KnowledgeBase
   from src.rag import store
   kb = KnowledgeBase()
   docs = {
     "lab-dense": "To merge semantic and keyword search, combine their ranked lists.",
     "lab-sparse": "Fix applies to firmware error code 0x81 specifically, not 0x80.",
   }
   for doc_id, text in docs.items():
       kb.add_document(text, {"type":"lab","doc_id":doc_id})
   ```
2. **Watch the channels disagree, then RRF reconcile:**
   ```python
   from src.rag import retriever, store, embeddings
   q = "error code 0x81"
   print("DENSE :", [r["doc_id"] for r in store.dense_search(embeddings.embed_one(q), 5)])
   print("SPARSE:", [r["doc_id"] for r in store.sparse_search(q, 5)])
   print("HYBRID:", [r["doc_id"] for r in retriever.hybrid_search(q, top_k=5)])
   ```
   Observe: the exact-code query is nailed by sparse; a conceptual query
   ("combine search methods") is nailed by dense; hybrid does well on both.
3. **Tune RRF:** set `RRF_K=10` in `.env`, restart your Python process, and compare ordering
   vs `RRF_K=60`. Explain the shift.
4. **(Optional) reranking:** set `RERANK_ENABLED=true`, re-run `hybrid_search(q, rerank=True)`,
   and note the latency increase and any ordering change.
5. **Cleanup:**
   ```python
   c = store.connect(); cur = c.cursor()
   cur.execute("DELETE FROM knowledge_chunks WHERE metadata->>'type'='lab'"); c.commit(); c.close()
   ```

## Checkpoint 5

**Concept check**
1. Why fuse on **rank** instead of normalizing and adding the raw scores?
2. What does lowering `k` in RRF do to the result ordering?
3. Why does chunk overlap exist?
4. When is the cross-encoder reranker worth its cost?

<details><summary>Answers</summary>

1. Cosine distance and `ts_rank_cd` are on different, non-comparable scales; normalizing is
   fragile. Ranks are universal, so RRF combines them without scale assumptions.
2. Lower `k` increases the weight of the very top ranks, sharpening precision toward
   documents that a channel ranked #1–#2 (helps exact-match queries).
3. So a fact spanning a chunk boundary isn't lost; the overlap keeps boundary context in at
   least one chunk.
4. When ranking quality matters more than latency — it reads query+passage jointly for higher
   precision but is much slower, so you enable it selectively.
</details>

**Practical task (pass criterion):** you can show one query where DENSE and SPARSE return
different top docs and HYBRID sensibly includes the right one; you can explain the effect of
`RRF_K=10` vs `60`; lab rows cleaned up. ✅
