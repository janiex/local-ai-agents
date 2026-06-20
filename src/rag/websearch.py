"""Web search fallback (DuckDuckGo, no API key).

Used when the knowledge base has nothing relevant for a task: we search the
web, hand the results to a researcher step that consolidates them into a
knowledge brief, and feed that brief to both agents.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..config import settings


def available() -> bool:
    try:
        import ddgs  # noqa: F401

        return True
    except Exception:
        try:
            import duckduckgo_search  # noqa: F401

            return True
        except Exception:
            return False


def search(query: str, max_results: int = None) -> List[Dict[str, Any]]:
    """Return a list of {title, body, url} results, or [] on any failure."""
    max_results = max_results or settings.web_search_results
    try:
        try:
            from ddgs import DDGS
        except Exception:  # fall back to the older package name
            from duckduckgo_search import DDGS

        out: List[Dict[str, Any]] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                out.append(
                    {
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "url": r.get("href") or r.get("url", ""),
                    }
                )
        return out
    except Exception:
        # Network down, package missing, rate-limited — degrade gracefully.
        return []


def format_results(results: List[Dict[str, Any]]) -> str:
    """Render results as a numbered list for the researcher prompt."""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}\n{r['body']}\n({r['url']})")
    return "\n\n".join(lines)
