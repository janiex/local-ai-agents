"""Local sentence-transformers embeddings (768-dim, runs offline).

Models are loaded lazily and cached at module level so the (slow) load happens
once per process regardless of how many callers ask for an embedder.
"""
from __future__ import annotations

from typing import List, Optional

from ..config import settings

_embedder = None
_reranker = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def embed(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts -> list of float vectors."""
    model = _get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> List[float]:
    return embed([text])[0]


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(settings.rerank_model)
    return _reranker


def rerank(query: str, passages: List[str]) -> List[float]:
    """Return a relevance score per passage (higher = more relevant)."""
    model = _get_reranker()
    scores = model.predict([(query, p) for p in passages])
    return [float(s) for s in scores]
