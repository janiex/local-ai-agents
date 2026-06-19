"""Postgres + pgvector store with two retrieval channels.

The InfoQ hybrid-retrieval design needs a *dense* channel (semantic kNN) and a
*sparse* channel (lexical / keyword). Both live in one Postgres table:

  * dense  -> pgvector `embedding vector(N)` with a cosine HNSW index
  * sparse -> a generated `tsv tsvector` column with a GIN index, ranked with
              `ts_rank_cd` (Postgres full-text — BM25-style lexical scoring)

Fusion (RRF) happens in `retriever.py`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import json

import psycopg2
import psycopg2.extras

from ..config import settings

TABLE = "knowledge_chunks"


def connect():
    return psycopg2.connect(settings.pg_dsn)


def _vec(values: List[float]) -> str:
    """Format a float vector as a pgvector text literal: '[1.0,2.0,...]'."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def init_schema(conn=None) -> None:
    """Create the extension, table and indexes (idempotent)."""
    own = conn is None
    conn = conn or connect()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    id          BIGSERIAL PRIMARY KEY,
                    doc_id      TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    metadata    JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding   vector({settings.embedding_dim}),
                    tsv         tsvector GENERATED ALWAYS AS
                                  (to_tsvector('english', content)) STORED,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {TABLE}_tsv_idx "
                f"ON {TABLE} USING GIN (tsv);"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {TABLE}_embedding_idx "
                f"ON {TABLE} USING hnsw (embedding vector_cosine_ops);"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {TABLE}_doc_id_idx ON {TABLE} (doc_id);"
            )
        conn.commit()
    finally:
        if own:
            conn.close()


def add_chunks(
    doc_id: str,
    chunks: List[str],
    embeddings: List[List[float]],
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    metadata = metadata or {}
    conn = connect()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {TABLE} (doc_id, content, metadata, embedding) VALUES %s",
                [
                    (doc_id, content, json.dumps(metadata), _vec(emb))
                    for content, emb in zip(chunks, embeddings)
                ],
                template="(%s, %s, %s::jsonb, %s::vector)",
            )
        conn.commit()
        return len(chunks)
    finally:
        conn.close()


def dense_search(query_embedding: List[float], limit: int) -> List[Dict[str, Any]]:
    """Semantic kNN via cosine distance (smaller = closer)."""
    conn = connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, doc_id, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM {TABLE}
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (_vec(query_embedding), _vec(query_embedding), limit),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def sparse_search(query: str, limit: int) -> List[Dict[str, Any]]:
    """Lexical / keyword search via Postgres full-text (BM25-style ranking)."""
    conn = connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, doc_id, content, metadata,
                       ts_rank_cd(tsv, query) AS score
                FROM {TABLE}, websearch_to_tsquery('english', %s) query
                WHERE tsv @@ query
                ORDER BY score DESC
                LIMIT %s;
                """,
                (query, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def stats() -> Dict[str, Any]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*), count(DISTINCT doc_id) FROM {TABLE};")
            chunks, docs = cur.fetchone()
        return {"chunks": chunks, "documents": docs}
    finally:
        conn.close()
