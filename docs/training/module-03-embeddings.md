# Module 3 — Embeddings and semantic search

**Goal:** understand how text becomes a vector, and how "similar meaning" becomes "small
distance."

**From embedded to here:** an embedding is a **feature vector** — like turning a raw sensor
waveform into a fixed-length descriptor (FFT bins, signature) so you can compare signals by
distance instead of sample-by-sample. Here the "sensor" is a neural net and the descriptor is
768 floats that encode *meaning*.

## Concepts

### 1. What an embedding is
A model maps a string to a fixed-length vector (here **768 dimensions**). Texts with similar
meaning land near each other in that 768-D space — even with no shared words. This is the
opposite of keyword matching, and its complementary weakness (see Module 5).

### 2. Cosine similarity
Similarity is measured by the **angle** between vectors, not their length. This project
**normalizes** embeddings (unit length) in [src/rag/embeddings.py](../../src/rag/embeddings.py)
(`normalize_embeddings=True`), so cosine similarity = dot product, and cosine *distance* =
`1 - cosine_similarity`. Smaller distance = more similar.

### 3. The model
`sentence-transformers/all-mpnet-base-v2` — 768-D, a solid general-purpose embedder that runs
locally and offline. It's loaded **lazily and cached** at module level so the slow load
happens once per process (a one-time init cost, like bringing up a peripheral).

### 4. Same model on both ends
Critical rule: you must embed **queries with the same model** you used to embed **documents**,
or the vectors live in different spaces and distances are meaningless. The project guarantees
this by routing everything through `embed()`.

## Hands-on lab

1. **Feel the geometry:**
   ```python
   from src.rag import embeddings
   import numpy as np
   v = embeddings.embed([
       "How do I combine keyword and vector search?",
       "Fuse lexical BM25 with dense retrieval results.",
       "My cat likes to sleep on the keyboard.",
   ])
   v = np.array(v)
   def cos(a, b): return float(a @ b)  # already normalized
   print("related :", round(cos(v[0], v[1]), 3))
   print("unrelated:", round(cos(v[0], v[2]), 3))
   ```
   Expected: the first pair scores clearly higher than the second, despite sharing few words.
2. **Confirm dimensionality and normalization:**
   ```python
   print(len(v[0]), round(float(np.linalg.norm(v[0])), 3))  # 768, ~1.0
   ```
3. **Break it on purpose:** embed a version number question ("error code 0x80 vs 0x81") and a
   semantically-near paraphrase, and note that embeddings see them as *very* similar even
   though the exact code differs. Write down why this is dangerous for exact-match queries —
   you'll fix it in Module 5 with the sparse channel.

## Checkpoint 3

**Concept check**
1. Why normalize embeddings? What does it let you substitute for cosine similarity?
2. Why must query and document embeddings use the same model?
3. Give one query type where embeddings are weak, and why.

<details><summary>Answers</summary>

1. Normalizing makes all vectors unit length, so cosine similarity equals the dot product
   (cheaper) and distance = 1 − dot. It also makes magnitudes comparable across texts.
2. Different models produce vectors in different, incompatible coordinate spaces; distances
   across spaces are meaningless. Same model = same space.
3. Exact-identifier queries (version numbers, error codes, SKUs): embeddings capture overall
   meaning and treat near-paraphrases as similar, so they don't reliably distinguish
   `0x80` from `0x81`. Keyword/sparse search handles those.
</details>

**Practical task (pass criterion):** your script prints a related-pair cosine noticeably
higher than the unrelated-pair cosine, vector length 768, norm ≈ 1.0. ✅
