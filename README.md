# 🤖 Toni & Sheriff — Two-Agent RAG System

A local-first AI system where **two agents debate your request** and consolidate a
decision, backed by a **hybrid-retrieval RAG knowledge base** that *learns from every
solution it produces*.

- **Toni** 🧠 — a solution architect that **proposes** an answer.
- **Sheriff** 🤠 — a critical reviewer that **challenges** Toni and applies critical thinking.
- They iterate round by round until Sheriff approves (or the round limit is hit), then
  **consolidate a final decision**.
- The consolidated solution is **accumulated into the knowledge base** and **retrieved at
  the start** of future tasks.

The retrieval layer implements the hybrid design from
[*Vector Search & Hybrid Retrieval for RAG* (InfoQ)](https://www.infoq.com/articles/vector-search-hybrid-retrieval-rag/):
**dense (semantic) + sparse (keyword) search fused with Reciprocal Rank Fusion (RRF)**,
plus an optional cross-encoder reranking stage.

---

## How it maps to the article

| Article concept | Implementation |
| --- | --- |
| Dense vector (kNN) search | `pgvector` cosine kNN with an HNSW index — `src/rag/store.py:dense_search` |
| Sparse / BM25 keyword search | Postgres full-text (`tsvector` + `ts_rank_cd`) — `src/rag/store.py:sparse_search` |
| Reciprocal Rank Fusion (k=60) | `src/rag/retriever.py:_reciprocal_rank_fusion` |
| Cross-encoder reranking (top 20–50) | optional, `src/rag/embeddings.py:rerank` (toggle in the UI / `.env`) |
| 768-dim embeddings, cosine | `sentence-transformers/all-mpnet-base-v2` |

> The sparse channel uses Postgres full-text search, which provides BM25-style lexical
> ranking natively in the database you already provision. For literal BM25, ParadeDB /
> `pg_search` is a drop-in upgrade path for `sparse_search`.

---

## Architecture

```
                 ┌──────────────── Streamlit UI (app.py) ────────────────┐
                 │  request · live Toni/Sheriff debate · user guidance    │
                 └───────────────────────────┬────────────────────────────┘
                                             │
                    ┌────────────────────────▼────────────────────────┐
                    │       DebateController  (src/agents)             │
                    │  start → toni_turn ↔ sheriff_turn → consolidate  │
                    └───────┬───────────────────────────────┬─────────┘
                            │ LLM                            │ RAG
              ┌─────────────▼─────────────┐     ┌────────────▼─────────────┐
              │  LLMProvider (src/llm)    │     │  KnowledgeBase (src/rag)  │
              │  • Ollama  (local)        │     │  hybrid retrieve + RRF    │
              │  • Anthropic (external)   │     │  accumulate solutions     │
              └───────────────────────────┘     └────────────┬─────────────┘
                                                              │
                                              ┌───────────────▼───────────────┐
                                              │  Postgres + pgvector (docker)  │
                                              │  dense kNN  +  full-text BM25  │
                                              └────────────────────────────────┘
```

LLM backend is **selectable at runtime** in the UI: fully **local via Ollama**, or the
**external Claude API** (`anthropic`). Embeddings always run locally so the RAG layer
works offline regardless of the chosen LLM.

---

## Setup

### 1. Requirements
- Python 3.9+
- Docker (for Postgres/pgvector)
- [Ollama](https://ollama.com) for the local LLM — or an `ANTHROPIC_API_KEY` for the external one

### 2. Install
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit if needed
```

### 3. Start the vector store
```bash
docker compose up -d        # Postgres + pgvector (see docker-compose.yml)
python -m scripts.init_db   # create the schema / indexes
```

### 4. Pick an LLM backend
**Local (default):**
```bash
ollama pull llama3.1        # or set OLLAMA_MODEL to another pulled model
```
**External (Claude):** choose `anthropic` in the sidebar and either paste your API key into
the sidebar field (session-only, not written to disk) or set `ANTHROPIC_API_KEY` in `.env`.

### 5. Run

The easiest way is the helper script, which brings up the Docker VM, Postgres,
and checks Ollama before launching the app (detached):

```bash
./run.sh start      # start services + app  → http://localhost:8501
./run.sh status     # show state of every component
./run.sh stop       # stop the app (services keep running)
./run.sh restart    # stop then start the app
./run.sh logs       # tail the app log
./run.sh down       # stop the app AND the Postgres container
```

`PORT=8600 ./run.sh start` runs on a different port. The app log lives at
`/tmp/local-ai-agents.streamlit.log`.

Or run it directly (services must already be up):

```bash
streamlit run app.py
```

---

## Using it

1. Type a request. Relevant **accumulated knowledge** is retrieved and shown.
2. Click **Run round** to watch Toni propose and Sheriff critique (streamed live). Add
   **optional guidance** before any round to steer the discussion.
3. When Sheriff approves (or rounds run out), click **Consolidate** for the final decision.
4. Click **Save to knowledge base** to accumulate the solution for future tasks.

---

## Configuration

All knobs live in `.env` (see `.env.example`): LLM provider/model, embedding model,
rerank toggle, RRF constant (`RRF_K`), candidate/top-k counts, debate rounds, and Postgres
connection. Most are also adjustable live in the sidebar.

---

## Project layout

```
app.py                  Streamlit UI
docker-compose.yml      Postgres + pgvector
scripts/init_db.py      one-time schema setup
src/
  config.py             env-driven settings
  llm/                  provider abstraction (ollama, anthropic) + factory
  rag/                  embeddings, chunking, pgvector store, hybrid retriever, KnowledgeBase
  agents/               prompts + Toni/Sheriff debate orchestrator
```

---

## Pushing to GitHub

`.env`, `.venv/`, and `__pycache__/` are gitignored. To publish:

```bash
git add .
git commit -m "Toni & Sheriff: two-agent hybrid-RAG system"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```
