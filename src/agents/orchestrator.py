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

from ..llm.base import LLMProvider
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
    retrieved: List[Dict[str, Any]] = field(default_factory=list)
    transcript: List[Turn] = field(default_factory=list)
    round: int = 0
    status: str = "new"       # new | toni | sheriff | done
    final_decision: str = ""

    # ---- setup -----------------------------------------------------------
    def start(self, rerank: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Retrieve accumulated knowledge for this task (the RAG 'beginning')."""
        self.retrieved = self.kb.retrieve(self.request, rerank=rerank)
        self.context = self.kb.format_context(self.retrieved)
        self.round = 1
        self.status = "toni"
        return self.retrieved

    # ---- transcript rendering -------------------------------------------
    def _render_transcript(self) -> str:
        lines = []
        for t in self.transcript:
            label = {"toni": "TONI", "sheriff": "SHERIFF", "final": "FINAL"}[t.agent]
            lines.append(f"--- {label} (round {t.round}) ---\n{t.content}")
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
