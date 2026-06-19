"""Lightweight text chunking (no external dependency).

Splits on blank lines, then greedily packs paragraphs up to `max_chars`,
carrying a small character overlap between chunks to preserve context across
boundaries.
"""
from __future__ import annotations

from typing import List


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            # Hard-split an oversized paragraph.
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(para), max_chars - overlap):
                chunks.append(para[i : i + max_chars])
            continue

        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = (tail + "\n\n" + para).strip()
        else:
            current = (current + "\n\n" + para).strip() if current else para

    if current:
        chunks.append(current)
    return chunks
