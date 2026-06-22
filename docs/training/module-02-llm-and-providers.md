# Module 2 — LLMs and the provider abstraction

**Goal:** explain what an LLM call actually is, and how this project swaps a local model for
a cloud API behind one interface.

**From embedded to here:** think of an LLM as a very large, read-only lookup function with
no internal state between calls — every request must carry the full context (like a stateless
protocol where each packet includes all needed headers). "Local vs cloud" is just *on-chip
peripheral vs external IC over a bus*: same interface, different latency, cost, and failure
modes.

## Concepts

### 1. Tokens and inference
Text is split into **tokens** (~¾ of a word each). The model predicts the next token
repeatedly to generate output. Practical implications you must design around:
- **Context window** = max tokens in + out (finite RAM-like budget). Long inputs cost more
  and can overflow.
- **Latency scales with output length** and model size; a 12B local model takes seconds to
  load and generate. This is why everything streams.
- **Statelessness:** the API remembers nothing — [src/agents/orchestrator.py](../../src/agents/orchestrator.py)
  resends the whole transcript each turn.

### 2. Prompting = the system + messages contract
A call has a **system prompt** (role/behavior) and a list of **messages**
(`{"role": "user"|"assistant", "content": ...}`). The agents' behavior lives almost entirely
in [src/agents/prompts.py](../../src/agents/prompts.py) — prompt text *is* the program here.

### 3. Local backend — Ollama
[src/llm/ollama_provider.py](../../src/llm/ollama_provider.py) POSTs to the local Ollama REST
API (`/api/chat`) with `stream: true` and parses newline-delimited JSON chunks. No API key,
runs offline. `health_check()` confirms the daemon is up and the model is pulled.

### 4. Cloud backend — Anthropic Claude
[src/llm/anthropic_provider.py](../../src/llm/anthropic_provider.py) uses the official SDK's
`messages.stream(...)` with `thinking={"type":"adaptive"}`. Same `stream()` signature as
Ollama → callers can't tell the difference.

### 5. The seam: factory + config
[src/llm/factory.py](../../src/llm/factory.py) picks the backend from a string; the API key
can come from `.env` ([src/config.py](../../src/config.py)) or be passed at call time (the UI
field). This is the dependency-inversion boundary that keeps the agents backend-agnostic.

## Hands-on lab

1. **See raw tokens streaming.** With Ollama up:
   ```bash
   curl -s http://localhost:11434/api/chat -d '{"model":"gemma3:12b","messages":[{"role":"user","content":"name 3 colors"}],"stream":true}'
   ```
   Watch the JSON chunks arrive — that's exactly what `OllamaProvider.stream` parses.
2. **Use the abstraction:**
   ```python
   from src.llm import get_provider
   p = get_provider("ollama")
   print(p.health_check())
   for chunk in p.stream("You are terse.", [{"role":"user","content":"Say hi in 3 words"}]):
       print(chunk, end="", flush=True)
   ```
3. **Prove backend-agnosticism:** write a function `summarize(provider, text)` that calls
   `provider.complete(...)`. Run it with the Ollama provider. (If you have a key, run the
   same function with `get_provider("anthropic")` — *no other change*.)
4. **Prompt sensitivity:** change the system prompt from "You are terse." to "You are
   verbose and academic." and observe the output difference. Note: same input, different
   behavior — that's the program living in the prompt.

## Checkpoint 2

**Concept check**
1. Why does the orchestrator resend the entire transcript on every turn?
2. Where would you change Sheriff's reviewing behavior — code or prompt? Which file?
3. What two things does `OllamaProvider.health_check()` verify, and why both?

<details><summary>Answers</summary>

1. The API is stateless; it has no memory of prior turns, so the full conversation must be
   sent each time to preserve context.
2. The prompt — `SHERIFF_SYSTEM` in [src/agents/prompts.py](../../src/agents/prompts.py).
3. That the Ollama daemon responds *and* that the configured model is actually pulled —
   a reachable daemon with a missing model would otherwise fail only at generation time.
</details>

**Practical task (pass criterion):** your `summarize(get_provider("ollama"), ...)` returns a
sensible summary, and you can state which single line you'd change to run it on Claude
instead. ✅
