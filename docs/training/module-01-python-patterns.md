# Module 1 — Python patterns used in this codebase

**Goal:** read any file in this project without getting stuck on unfamiliar Python idioms.

**From embedded to here:** you already use these ideas, just with different names. An
abstract base class is a *HAL/driver interface* (a vtable of functions a board must
implement). A generator is a *producer feeding a ring buffer* — it yields items lazily
instead of returning everything at once. A context manager (`with`) is *acquire/release*
(like taking a mutex or opening a peripheral and guaranteeing you close it). Dataclasses are
*structs with defaults*.

## Concepts (with the project's own examples)

### 1. Dataclasses = structs
[src/config.py](../../src/config.py) defines `Settings` as a `@dataclass`: a typed struct
whose fields default from environment variables. [src/agents/orchestrator.py](../../src/agents/orchestrator.py)
uses `@dataclass` for `DebateController` to hold mutable session state (transcript, round,
status). `field(default_factory=list)` is how you give each instance its *own* list (the
Python equivalent of not sharing a static buffer between instances — a classic bug if you
used a bare `[]` default).

### 2. Type hints + `from __future__ import annotations`
Hints like `List[Dict[str, Any]]` are documentation the tools check; they don't change
runtime behavior. The `from __future__ import annotations` line at the top of most files
makes annotations lazy strings so newer syntax works on Python 3.9. Treat hints as the
*function's contract*, like a header file's prototypes.

### 3. Abstract base classes (interfaces)
[src/llm/base.py](../../src/llm/base.py) declares `LLMProvider(ABC)` with an abstract
`stream(...)`. Any backend (Ollama, Anthropic) must implement it — exactly like a driver
implementing a HAL. Code that depends on `LLMProvider` doesn't care which backend it got.
Note `complete()` is a concrete default built *on top of* `stream()` — one required
primitive, free derived behavior.

### 4. Generators and streaming (`yield`)
`stream()` returns an **iterator of text chunks** via `yield`. The caller consumes them as
they arrive (token by token), like draining a FIFO. This is why the UI can show text
appearing live. Two consequences to internalize:
- A generator does nothing until iterated (lazy).
- Side effects inside a generator run *as it's consumed* — in `toni_turn()`, the transcript
  is appended only after the loop finishes draining the stream.

### 5. Context managers (`with`)
`with requests.post(...) as resp:` and `with self._client.messages.stream(...) as stream:`
guarantee the connection is closed even on error — acquire/release with a built-in `finally`.

### 6. The factory function
[src/llm/factory.py](../../src/llm/factory.py) `get_provider(name)` returns the right
concrete class for a string. This is the *board-select* pattern: one place decides which
implementation you get, callers stay generic.

## Hands-on lab

1. Open [src/llm/base.py](../../src/llm/base.py) and [ollama_provider.py](../../src/llm/ollama_provider.py).
   Trace how `complete()` works without `OllamaProvider` defining it.
2. Write a tiny generator and prove laziness:
   ```python
   def gen():
       print("start")
       for i in range(3):
           yield i
   g = gen()              # nothing prints yet
   print("created")
   print(list(g))         # now "start" prints, then [0,1,2]
   ```
3. Add a 5-line **mock provider** in a scratch file that implements `LLMProvider` and yields
   a fixed string word-by-word, then run it through `complete()`:
   ```python
   from src.llm.base import LLMProvider
   class EchoProvider(LLMProvider):
       name = "echo"
       def stream(self, system, messages):
           for w in ("hello", " ", "world"):
               yield w
   print(EchoProvider().complete("sys", [{"role":"user","content":"hi"}]))
   ```

## Checkpoint 1

**Concept check**
1. Why does `DebateController` use `field(default_factory=list)` instead of `= []`?
2. What is the difference between `stream()` and `complete()` and why is only one abstract?
3. When do the side effects inside a generator actually execute?

<details><summary>Answers</summary>

1. A bare `[]` default is created once and shared by all instances (mutable default
   argument trap), so every controller would mutate the same list. `default_factory=list`
   gives each instance a fresh list.
2. `stream()` yields chunks incrementally and is the required primitive; `complete()` is a
   concrete helper that joins the stream into one string. Only `stream()` is abstract so
   each backend implements the minimum.
3. Only while the generator is being iterated/consumed — not when it's created.
</details>

**Practical task (pass criterion):** your `EchoProvider().complete(...)` returns
`"hello world"`. You did not modify `base.py`. ✅
