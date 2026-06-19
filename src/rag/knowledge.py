"""High-level knowledge base facade used by the agents and UI.

Responsibilities:
  * retrieve relevant accumulated knowledge at the *start* of a task
  * accumulate (ingest) the consolidated solution *after* a task is decided
"""
from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any, Dict, List

from . import chunking, embeddings, retriever, store


class KnowledgeBase:
    def __init__(self):
        # Ensure the schema exists; cheap and idempotent.
        store.init_schema()

    # ---- retrieval (used at the beginning of a task) ----------------------
    def retrieve(self, query: str, top_k: int = None, rerank: bool = None) -> List[Dict[str, Any]]:
        return retriever.hybrid_search(query, top_k=top_k, rerank=rerank)

    def format_context(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return ""
        blocks = []
        for i, r in enumerate(results, 1):
            meta = r.get("metadata") or {}
            src = meta.get("request") or meta.get("title") or r.get("doc_id", "")
            blocks.append(f"[K{i}] (from prior solution: {src})\n{r['content']}")
        return "\n\n".join(blocks)

    # ---- accumulation (used after a solution is agreed) -------------------
    def add_document(self, text: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        metadata = metadata or {}
        doc_id = metadata.get("doc_id") or str(uuid.uuid4())
        chunks = chunking.chunk_text(text)
        if not chunks:
            return {"doc_id": doc_id, "chunks": 0}
        vectors = embeddings.embed(chunks)
        store.add_chunks(doc_id, chunks, vectors, metadata)
        return {"doc_id": doc_id, "chunks": len(chunks)}

    def accumulate_solution(self, request: str, final_decision: str,
                            transcript_summary: str = "") -> Dict[str, Any]:
        """Persist an agreed solution as reusable knowledge."""
        timestamp = _dt.datetime.utcnow().isoformat()
        body = (
            f"# Solution knowledge\n\n"
            f"## Original request\n{request}\n\n"
            f"## Consolidated decision (Toni + Sheriff)\n{final_decision}\n"
        )
        if transcript_summary:
            body += f"\n## Key reasoning\n{transcript_summary}\n"
        return self.add_document(
            body,
            metadata={
                "type": "solution",
                "request": request,
                "created_at": timestamp,
            },
        )

    def stats(self) -> Dict[str, Any]:
        return store.stats()
