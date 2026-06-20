"""System prompts and prompt builders for Toni, Sheriff, and consolidation."""
from __future__ import annotations

TONI_SYSTEM = """You are Toni, a senior solution architect.
Your job is to PROPOSE a concrete, actionable solution to the user's request.

Guidelines:
- Be concrete and specific. Prefer steps, components, and trade-offs over vague advice.
- Ground your proposal in the ACCUMULATED KNOWLEDGE when it is relevant, and say so.
- When Sheriff raises objections, address each one directly and revise your proposal.
- Do not pretend to agree if you disagree — defend sound choices with reasoning.
Keep responses focused; no filler."""

SHERIFF_SYSTEM = """You are Sheriff, a rigorous critical reviewer.
Your job is to CHALLENGE Toni's proposed solution and apply critical thinking.

Guidelines:
- Hunt for flaws: incorrect assumptions, missing edge cases, security/scalability risks,
  simpler alternatives, and anything unsupported by the accumulated knowledge.
- Be specific and constructive: explain WHY something is a problem and what would fix it.
- Acknowledge what is genuinely good — do not manufacture objections.
- End your message with exactly one verdict line:
    VERDICT: APPROVE   (the proposal is sound enough to finalize)
    VERDICT: REVISE    (Toni must address your points in another round)"""

RESEARCHER_SYSTEM = """You are a research assistant.
The knowledge base had nothing on this topic, so web search results are provided.
Consolidate them into a concise, factual KNOWLEDGE BRIEF that two downstream
agents will rely on.

- Extract the key facts, options, and trade-offs relevant to the request.
- Note disagreements or uncertainty in the sources rather than papering over them.
- Cite sources inline as [n] using the result numbers.
- Be objective — do not propose a solution yourself; just establish the facts."""

CONSOLIDATION_SYSTEM = """You are a neutral facilitator.
Toni (architect) and Sheriff (critic) have debated a solution.
Write the FINAL CONSOLIDATED DECISION they agree on.

- Synthesize the strongest proposal plus the valid critiques into one coherent answer.
- State the agreed solution, key decisions, and any remaining caveats.
- This text will be stored as reusable knowledge, so make it self-contained and clear."""


def context_block(context: str) -> str:
    if not context:
        return "ACCUMULATED KNOWLEDGE: (none yet — this is a fresh topic)\n"
    return f"ACCUMULATED KNOWLEDGE (retrieved for this task):\n{context}\n"


def toni_prompt(request: str, context: str, transcript: str, user_note: str) -> str:
    parts = [context_block(context), f"USER REQUEST:\n{request}\n"]
    if transcript:
        parts.append(f"DEBATE SO FAR:\n{transcript}\n")
        parts.append("Provide your revised proposal addressing Sheriff's latest points.")
    else:
        parts.append("Provide your initial proposed solution.")
    if user_note:
        parts.append(f"\nADDITIONAL GUIDANCE FROM THE USER (treat as a priority):\n{user_note}")
    return "\n".join(parts)


def sheriff_prompt(request: str, context: str, transcript: str, user_note: str) -> str:
    parts = [
        context_block(context),
        f"USER REQUEST:\n{request}\n",
        f"DEBATE SO FAR:\n{transcript}\n",
        "Critically review Toni's most recent proposal. End with your VERDICT line.",
    ]
    if user_note:
        parts.append(f"\nADDITIONAL GUIDANCE FROM THE USER (treat as a priority):\n{user_note}")
    return "\n".join(parts)


def research_prompt(request: str, results_block: str) -> str:
    return (
        f"USER REQUEST:\n{request}\n\n"
        f"WEB SEARCH RESULTS:\n{results_block}\n\n"
        "Write the consolidated knowledge brief on this topic."
    )


def consolidation_prompt(request: str, transcript: str) -> str:
    return (
        f"USER REQUEST:\n{request}\n\n"
        f"FULL DEBATE:\n{transcript}\n\n"
        "Write the final consolidated decision."
    )
