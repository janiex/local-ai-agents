# Module 6 — Multi-agent orchestration (Toni & Sheriff)

**Goal:** model a two-agent debate that converges on a decision as an explicit state machine,
and understand why critique-then-consolidate beats a single LLM call.

**From embedded to here:** this is a **state machine driving two cooperating tasks**. Toni and
Sheriff are like two RTOS tasks exchanging messages; the controller is the scheduler that
sequences them, checks a guard condition (Sheriff's verdict), and transitions until a
terminal state. You already think in states, guards, and transitions — apply that directly.

## Concepts

### 1. Why two agents
A single LLM answer is confident but unchecked. Splitting into a **proposer** (Toni) and a
**critic** (Sheriff) creates an adversarial check that surfaces flaws before they reach the
user — like design + review, or generate + self-test. The consolidation step then merges the
strongest proposal with the valid critiques.

### 2. The state machine
[src/agents/orchestrator.py](../../src/agents/orchestrator.py) `DebateController.status` moves:
```
new ──start()──► (rag? ► toni) | (web? ► research ► toni) | (none ► toni)
toni ──toni_turn()──► sheriff
sheriff ──sheriff_turn()──► toni (REVISE, if rounds left) | done (APPROVE or max rounds)
done ──consolidate()──► final decision ──save_to_knowledge() [explicit]
```
Each transition is one method that **streams** its output (Module 1's generators) and then
updates `status`, `round`, and `transcript`.

### 3. The guard: parsing a verdict
Sheriff is prompted to end with `VERDICT: APPROVE` or `VERDICT: REVISE`
([prompts.py](../../src/agents/prompts.py)). `_parse_verdict()` extracts it and **defaults to
REVISE** if unclear — a safe default (one more review round) rather than a false approval.
This is defensive parsing of a probabilistic output: never trust the model to be perfectly
formatted.

### 4. Context assembly
Every turn rebuilds a prompt from: retrieved knowledge (or web brief), the user request, the
running transcript, and optional user guidance. Because the LLM is stateless, the transcript
*is* the memory (Module 2).

### 5. Termination guarantees
The loop is bounded by `MAX_DEBATE_ROUNDS` — like a watchdog/iteration cap so a stubborn
disagreement can't loop forever. Always bound LLM loops.

### 6. UI-agnostic by design
The controller has no Streamlit imports. The UI (Module 7) and any future front-end
(WhatsApp, CLI) just call `start → toni_turn → sheriff_turn → consolidate → save`. This is
why the engine is reusable.

## Hands-on lab

Drive the controller directly, no UI:
```python
from src.llm import get_provider
from src.rag.knowledge import KnowledgeBase
from src.agents import DebateController

ctrl = DebateController(provider=get_provider("ollama"), kb=KnowledgeBase(),
                        request="Design a bounded retry policy for a flaky sensor read",
                        max_rounds=2)
ctrl.start()
print("source:", ctrl.source, "status:", ctrl.status)

print("\n--- TONI ---")
for c in ctrl.toni_turn(): print(c, end="", flush=True)
print("\n--- SHERIFF ---")
for c in ctrl.sheriff_turn(): print(c, end="", flush=True)
print("\nverdict:", ctrl.transcript[-1].verdict, "next status:", ctrl.status)

while ctrl.status in ("toni","sheriff"):
    turn = ctrl.toni_turn if ctrl.status=="toni" else ctrl.sheriff_turn
    for c in turn(): pass
print("\n--- CONSOLIDATED ---")
for c in ctrl.consolidate(): print(c, end="", flush=True)
# NOTE: not calling save_to_knowledge() — saving is explicit/opt-in
```
Then:
1. Add `user_note="must run with no dynamic memory allocation"` to a `toni_turn(...)` call and
   see it steer the proposal.
2. Force a malformed verdict mentally: read `_parse_verdict` and explain what happens if
   Sheriff forgets the verdict line.
3. Inspect `ctrl._render_transcript()` — this exact text is what `save_to_knowledge()` would
   persist.

## Checkpoint 6

**Concept check**
1. What are the states and the guard condition that ends the debate?
2. Why does `_parse_verdict` default to `REVISE`?
3. Where is the debate's "memory" between turns, and why there?
4. Name one reason the controller imports nothing from Streamlit.

<details><summary>Answers</summary>

1. States: `new/toni/sheriff/done` (plus `research`). The guard is Sheriff's verdict —
   `APPROVE` (or hitting `max_rounds`) → `done`; otherwise another `toni` round.
2. Because a missing/ambiguous verdict shouldn't be read as approval; defaulting to one more
   review round is the safe failure mode.
3. In `transcript` (rebuilt into each prompt) — because the LLM API is stateless and keeps no
   server-side memory.
4. So the same engine can be driven by any front-end (Streamlit, WhatsApp, CLI, tests)
   without modification.
</details>

**Practical task (pass criterion):** your script runs a full debate to a consolidated
decision via the controller API only (no UI), and you did **not** call
`save_to_knowledge()`. You can point to the line where the verdict guard is evaluated. ✅
