"""Hybrid retrieval: parallel dense + sparse, fused with Reciprocal Rank Fusion.

Implements the architecture from the InfoQ article:
  1. run BM25-style (sparse) and kNN (dense) searches over the same candidates
  2. fuse the two ranked lists with RRF: score(d) = sum 1 / (k + rank_r(d))
  3. optionally rerank the fused top candidates with a cross-encoder
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..config import settings
from . import embeddings, store


def _reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]], k: int
) -> List[Dict[str, Any]]:
    fused: Dict[int, Dict[str, Any]] = {}
    for ranked in ranked_lists:
        for rank, row in enumerate(ranked):
            rid = row["id"]
            if rid not in fused:
                fused[rid] = {**row, "rrf_score": 0.0}
            fused[rid]["rrf_score"] += 1.0 / (k + rank + 1)
    return sorted(fused.values(), key=lambda r: r["rrf_score"], reverse=True)


def hybrid_search(
    query: str,
    top_k: int = None,
    *,
    rerank: bool = None,
) -> List[Dict[str, Any]]:
    top_k = top_k or settings.retrieval_top_k
    rerank = settings.rerank_enabled if rerank is None else rerank
    candidates = settings.retrieval_candidates

    dense = store.dense_search(embeddings.embed_one(query), candidates)
    sparse = store.sparse_search(query, candidates)

    fused = _reciprocal_rank_fusion([dense, sparse], settings.rrf_k)
    if not fused:
        return []

    if rerank:
        pool = fused[: max(top_k, 20)]
        scores = embeddings.rerank(query, [r["content"] for r in pool])
        for row, s in zip(pool, scores):
            row["rerank_score"] = s
        pool.sort(key=lambda r: r["rerank_score"], reverse=True)
        return pool[:top_k]

    return fused[:top_k]
