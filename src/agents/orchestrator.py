"""Drives the Toni <-> Sheriff debate toward a consolidated decision.

UI-agnostic and *step-based*: the Streamlit app calls `toni_turn`, `sheriff_turn`
and `consolidate` one at a time, streaming each, so the user can observe the
discussion live and inject guidance between rounds.

Flow per task:
  start()  -> retrieve accumulated knowledge (used at the beginning)
  round N: toni_turn() then sheriff_turn() (verdict APPROVE | REVISE)
  consolidate() -> final decision, then accumulate_solution() stores it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from ..config import settings
from ..llm.base import LLMProvider
from ..rag import websearch
from ..rag.knowledge import KnowledgeBase
from . import prompts


@dataclass
class Turn:
    agent: str            # "toni" | "sheriff" | "final"
    round: int
    content: str
    verdict: Optional[str] = None  # for sheriff: "APPROVE" | "REVISE"


@dataclass
class DebateController:
    provider: LLMProvider
    kb: KnowledgeBase
    request: str
    max_rounds: int = 3

    context: str = ""
    source: str = "none"      # where context came from: rag | web | none
    retrieved: List[Dict[str, Any]] = field(default_factory=list)
    web_results: List[Dict[str, Any]] = field(default_factory=list)
    transcript: List[Turn] = field(default_factory=list)
    round: int = 0
    status: str = "new"       # new | research | toni | sheriff | done
    final_decision: str = ""

    # ---- setup -----------------------------------------------------------
    def start(self, rerank: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Begin a task: retrieve accumulated knowledge, else fall back to web.

        If the knowledge base has relevant chunks, use them. Otherwise run a web
        search; a researcher step (`research_turn`) will consolidate the results
        into a brief that feeds both agents.
        """
        self.retrieved = self.kb.retrieve(self.request, rerank=rerank)
        if self.retrieved:
            self.context = self.kb.format_context(self.retrieved)
            self.source = "rag"
            self.round = 1
            self.status = "toni"
            return self.retrieved

        # Nothing in the KB — try the web.
        if settings.web_search_enabled:
            self.web_results = websearch.search(self.request)
        if self.web_results:
            self.source = "web"
            self.status = "research"   # research_turn() builds the context next
        else:
            self.source = "none"
            self.context = ""
            self.round = 1
            self.status = "toni"
        return self.retrieved

    # ---- research (web fallback) ----------------------------------------
    def research_turn(self) -> Iterator[str]:
        """Consolidate web results into a knowledge brief, shared by both agents."""
        results_block = websearch.format_results(self.web_results)
        prompt = prompts.research_prompt(self.request, results_block)
        buf = []
        for chunk in self.provider.stream(
            prompts.RESEARCHER_SYSTEM, [{"role": "user", "content": prompt}]
        ):
            buf.append(chunk)
            yield chunk
        brief = "".join(buf)
        self.context = brief
        self.transcript.append(Turn("researcher", 0, brief))
        # Nothing is persisted here — the brief stays in-session and is only
        # written to the KB if the user later clicks "Save to knowledge base"
        # (it is captured in the saved transcript summary).
        self.round = 1
        self.status = "toni"

    # ---- transcript rendering -------------------------------------------
    def _render_transcript(self) -> str:
        lines = []
        labels = {"researcher": "RESEARCH BRIEF", "toni": "TONI",
                  "sheriff": "SHERIFF", "final": "FINAL"}
        for t in self.transcript:
            lines.append(f"--- {labels[t.agent]} (round {t.round}) ---\n{t.content}")
        return "\n\n".join(lines)

    # ---- agent turns (generators that stream) ----------------------------
    def toni_turn(self, user_note: str = "") -> Iterator[str]:
        prompt = prompts.toni_prompt(
            self.request, self.context, self._render_transcript(), user_note
        )
        buf = []
        for chunk in self.provider.stream(prompts.TONI_SYSTEM, [{"role": "user", "content": prompt}]):
            buf.append(chunk)
            yield chunk
        self.transcript.append(Turn("toni", self.round, "".join(buf)))
        self.status = "sheriff"

    def sheriff_turn(self, user_note: str = "") -> Iterator[str]:
        prompt = prompts.sheriff_prompt(
            self.request, self.context, self._render_transcript(), user_note
        )
        buf = []
        for chunk in self.provider.stream(prompts.SHERIFF_SYSTEM, [{"role": "user", "content": prompt}]):
            buf.append(chunk)
            yield chunk
        content = "".join(buf)
        verdict = self._parse_verdict(content)
        self.transcript.append(Turn("sheriff", self.round, content, verdict=verdict))

        if verdict == "APPROVE" or self.round >= self.max_rounds:
            self.status = "done"
        else:
            self.round += 1
            self.status = "toni"

    def consolidate(self) -> Iterator[str]:
        prompt = prompts.consolidation_prompt(self.request, self._render_transcript())
        buf = []
        for chunk in self.provider.stream(
            prompts.CONSOLIDATION_SYSTEM, [{"role": "user", "content": prompt}]
        ):
            buf.append(chunk)
            yield chunk
        self.final_decision = "".join(buf)
        self.transcript.append(Turn("final", self.round, self.final_decision))

    # ---- accumulation ----------------------------------------------------
    def save_to_knowledge(self) -> Dict[str, Any]:
        """Persist the consolidated solution for future tasks."""
        summary = self._render_transcript()[:4000]
        return self.kb.accumulate_solution(self.request, self.final_decision, summary)

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _parse_verdict(text: str) -> str:
        upper = text.upper()
        idx = upper.rfind("VERDICT")
        if idx != -1:
            tail = upper[idx:]
            if "APPROVE" in tail:
                return "APPROVE"
            if "REVISE" in tail:
                return "REVISE"
        return "REVISE"  # default to another round if unclear
