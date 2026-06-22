# Module 7 — Application layer and service lifecycle

**Goal:** understand Streamlit's reactive execution model, how the UI drives the controller
step by step, and how the whole stack is brought up and torn down.

**From embedded to here:** Streamlit's "re-run the whole script on every interaction" is like
a **superloop that re-renders from state each tick** — the UI is a pure function of
`session_state`, and you mutate state in event handlers (button callbacks) much like setting
flags an ISR reads next loop. The lifecycle script is your **board bring-up sequence**:
power the dependencies in order, wait for ready, then start the app.

## Concepts

### 1. Streamlit's reactive model
[app.py](../../app.py) runs **top to bottom on every interaction**. Persistent state lives in
`st.session_state` (e.g., the `DebateController`). So the pattern is:
- render the transcript *from state* each run,
- only do new work (an LLM turn) inside a button branch,
- then `st.rerun()` so the new state renders.
`@st.cache_resource` keeps heavy objects (the `KnowledgeBase`, embedder) alive across re-runs
— without it you'd reconnect/reload every click.

### 2. Streaming into the UI
`st.write_stream(generator)` consumes a controller turn's generator and renders tokens live —
the same generator the headless lab in Module 6 consumed. One engine, two consumers.

### 3. Human-in-the-loop = explicit buttons
Buttons map to controller transitions: **Run round** → `toni_turn`/`sheriff_turn`,
**Consolidate** → `consolidate`, **Save to knowledge base** → `save_to_knowledge` (the only
write of session knowledge; opt-in by design). The sidebar handles config and the separate
**URL ingest** path (Module 8).

### 4. Service topology
Four components (see the architecture diagram in the root [README](../../README.md)):
- **colima** — the Docker VM (macOS).
- **Postgres + pgvector** — the store ([docker-compose.yml](../../docker-compose.yml),
  `restart: unless-stopped` + healthcheck).
- **Ollama** — the local LLM server (brew service).
- **Streamlit app** — the UI process.

### 5. The lifecycle script
[run.sh](../../run.sh) is the single control surface:
`start | stop | restart | status | logs | down | shutdown`. `start` calls `ensure_services()`
(bring up colima → Postgres → run `init_db` → Ollama, **each only if needed**), then launches
Streamlit detached with `nohup` and waits for HTTP 200. `shutdown` is the symmetric teardown.
`scripts/init_db.py` ([here](../../scripts/init_db.py)) creates the schema idempotently.

### 6. Detached process gotcha (worth knowing)
The app is started with `nohup ... & disown` so it survives the launching shell. A process
started under a transient task manager would be reaped when that task ends — a subtle
lifecycle bug that detaching avoids.

## Hands-on lab

1. **Read the reactive loop:** in [app.py](../../app.py), find where `st.session_state.controller`
   is created, where the transcript is re-rendered each run, and where `st.rerun()` is called
   after a turn. Write a 3-line summary of the control flow.
2. **Exercise the lifecycle:**
   ```bash
   ./run.sh status
   ./run.sh stop      # app only
   ./run.sh status    # app stopped, services still up
   ./run.sh start     # app back; services were already up so no re-init
   ```
3. **Full symmetry:** `./run.sh shutdown` then `./run.sh status` (all stopped) then
   `./run.sh start` (cold bring-up). Time the cold start and note which step dominates.
4. **Add a read-only widget:** add a sidebar `st.metric` showing the current KB document count
   (`get_kb().stats()["documents"]`). Reload the page and confirm it renders. Revert when done.

## Checkpoint 7

**Concept check**
1. Why must you render the transcript from `session_state` rather than from local variables?
2. What does `@st.cache_resource` prevent on every re-run?
3. In what order does `ensure_services()` bring things up, and why that order?
4. Why is the app launched with `nohup`/`disown`?

<details><summary>Answers</summary>

1. Streamlit re-runs the whole script each interaction; local variables are recreated, so
   only `session_state` survives across runs to hold the debate.
2. Reconnecting to Postgres and reloading the embedding model (and re-creating the
   `KnowledgeBase`) on every click — it caches those heavy objects.
3. colima (Docker VM) → Postgres (needs Docker) → schema init (needs Postgres) → Ollama →
   app. Each depends on the previous being ready.
4. So the server detaches from the launching shell/task and keeps running across turns
   instead of being killed when the parent exits.
</details>

**Practical task (pass criterion):** you complete the stop/start and shutdown/start cycles
with `status` reflecting each state correctly, and your temporary KB-count `st.metric`
rendered in the sidebar. ✅
