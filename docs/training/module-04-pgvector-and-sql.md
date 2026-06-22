# Module 4 — Vectors in Postgres (pgvector + SQL)

**Goal:** store and query both vectors and full text in one database, and reason about the
indexes that make it fast.

**From embedded to here:** a vector index (HNSW) is a **navigable lookup structure** — like a
spatial data structure or a routing table that gets you *approximately* to the nearest entry
without scanning every row. You trade a little accuracy for a huge speedup, exactly the kind
of bounded approximation you already make under timing constraints.

## Concepts

### 1. One table, two retrieval modalities
[src/rag/store.py](../../src/rag/store.py) `init_schema()` creates `knowledge_chunks`:
- `embedding vector(768)` — the dense/semantic column (pgvector extension).
- `tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED` — a derived
  full-text column, kept in sync automatically by Postgres (a computed column — set once,
  never update by hand).
- `metadata jsonb` — flexible per-chunk attributes (type, source, request…).

### 2. Indexes
- `USING hnsw (embedding vector_cosine_ops)` — approximate nearest-neighbor for the vector
  column, cosine metric. Without it, similarity search scans every row.
- `USING GIN (tsv)` — inverted index for full-text, the classic structure for "which rows
  contain these terms."
Both are created idempotently, so re-running init is safe.

### 3. The two queries
- **Dense** (`dense_search`): `ORDER BY embedding <=> %s::vector LIMIT k`. The `<=>` operator
  is cosine distance; smaller is closer. Score is reported as `1 - distance`.
- **Sparse** (`sparse_search`): `websearch_to_tsquery('english', q)` + `ts_rank_cd(tsv, query)`
  — Postgres full-text, a BM25-style lexical ranking.

### 4. Driver detail you must respect
Vectors are passed as a text literal `'[0.1,0.2,...]'` cast with `::vector` (`_vec()` in
store.py), not as a Python list — psycopg2 would otherwise serialize a list as a SQL array
and the cast fails. This is the kind of marshalling boundary embedded devs know well.

### 5. Why Postgres for both
Keeping dense + sparse in the *same* store means one transaction, one connection, one ops
surface — and the hybrid fusion (Module 5) just reads two result sets from one DB.

## Hands-on lab

Use `psql` inside the container (no extra install):
```bash
docker exec -it local-pgvector psql -U agent_user -d agent_db
```
1. Inspect the schema and indexes:
   ```sql
   \d+ knowledge_chunks
   \di
   ```
2. Add two rows (note: real inserts go through `add_chunks`, but do this to see the SQL):
   ```sql
   INSERT INTO knowledge_chunks (doc_id, content, embedding)
   VALUES ('t','hybrid search fuses BM25 and vectors', (SELECT '['||array_to_string(array_fill(0.01::float,'{768}'),',')||']')::vector),
          ('t','cats sleep a lot', (SELECT '['||array_to_string(array_fill(0.02::float,'{768}'),',')||']')::vector);
   ```
3. Run a **sparse** query and read the ranking:
   ```sql
   SELECT content, ts_rank_cd(tsv, q) AS score
   FROM knowledge_chunks, websearch_to_tsquery('english','bm25 vectors') q
   WHERE tsv @@ q ORDER BY score DESC;
   ```
4. Clean up: `DELETE FROM knowledge_chunks WHERE doc_id='t';`
5. Back in Python, run the real path and notice it returns the same row shape the retriever
   consumes:
   ```python
   from src.rag import store, embeddings
   store.add_chunks("lab", ["RRF combines ranked lists by position"], embeddings.embed(["RRF combines ranked lists by position"]), {"type":"lab"})
   print(store.sparse_search("reciprocal rank fusion", 3))
   print(store.dense_search(embeddings.embed_one("how to merge result rankings"), 3))
   # cleanup
   import psycopg2
   c = store.connect();  cur = c.cursor(); cur.execute("DELETE FROM knowledge_chunks WHERE doc_id='lab'"); c.commit(); c.close()
   ```

## Checkpoint 4

**Concept check**
1. What does the `<=>` operator compute, and does smaller mean more or less similar?
2. Why is `tsv` a `GENERATED` column instead of one the app writes?
3. Why pass embeddings as `'[...]'::vector` rather than a Python list?
4. What does HNSW trade away for speed, and why is that acceptable here?

<details><summary>Answers</summary>

1. Cosine distance between the stored vector and the query vector; smaller = more similar.
2. It's derived deterministically from `content`, so Postgres maintains it automatically and
   it can never drift out of sync with the text.
3. psycopg2 would adapt a Python list to a SQL array literal (`{...}`) which won't cast to
   `vector`; the explicit `'[...]'::vector` text literal casts correctly.
4. Exactness — HNSW is *approximate* nearest neighbor; it can occasionally miss the true
   top-k. Acceptable because retrieval feeds an LLM that tolerates near-misses, and the speed
   gain over a full scan is large.
</details>

**Practical task (pass criterion):** in `psql`, your sparse query ranks the "bm25 vectors"
row above the "cats" row; in Python, `sparse_search` and `dense_search` each return rows with
`id, content, metadata, score`; you cleaned up the lab rows. ✅
