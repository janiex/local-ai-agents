"""Toni & Sheriff — Streamlit UI.

Define a request, watch Toni propose and Sheriff critique it round by round,
inject your own guidance between rounds, and let them consolidate a final
decision that is accumulated into the RAG knowledge base for future tasks.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from src.config import settings
from src.llm import available_providers, get_provider
from src.agents import DebateController

AVATARS = {"toni": "🧠", "sheriff": "🤠", "final": "🤝"}

st.set_page_config(page_title="Toni & Sheriff — RAG agents", page_icon="🤖", layout="wide")


# --------------------------------------------------------------------------
# Cached heavy resources
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Connecting to knowledge base…")
def get_kb():
    from src.rag.knowledge import KnowledgeBase

    return KnowledgeBase()


def build_provider(provider_name: str, model: str, api_key: str = ""):
    return get_provider(provider_name, model=model or None, api_key=api_key or None)


# --------------------------------------------------------------------------
# Sidebar — configuration
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")

    provider_name = st.selectbox(
        "LLM backend",
        available_providers(),
        index=available_providers().index(settings.llm_provider)
        if settings.llm_provider in available_providers()
        else 0,
        help="`ollama` runs locally; `anthropic` calls the external Claude API.",
    )
    api_key = ""
    if provider_name == "ollama":
        model = st.text_input("Ollama model", value=settings.ollama_model)
    else:
        model = st.text_input("Anthropic model", value=settings.anthropic_model)
        api_key = st.text_input(
            "Anthropic API key",
            value=settings.anthropic_api_key,
            type="password",
            help="Used only for this session — not written to disk. "
            "Falls back to ANTHROPIC_API_KEY in .env if left blank.",
        )
        if not api_key:
            st.warning("Enter an API key (or set ANTHROPIC_API_KEY in .env) to use Claude.")

    st.divider()
    st.subheader("Retrieval")
    rerank = st.toggle(
        "Cross-encoder rerank", value=settings.rerank_enabled,
        help="Article step 3: rerank fused candidates (slower, more accurate).",
    )
    top_k = st.slider("Top-k context chunks", 1, 15, settings.retrieval_top_k)
    max_rounds = st.slider("Max debate rounds", 1, 6, settings.max_debate_rounds)

    st.divider()
    if st.button("🔌 Test backends"):
        try:
            msg = build_provider(provider_name, model, api_key).health_check()
            st.success(f"LLM: {msg}")
        except Exception as e:  # noqa: BLE001
            st.error(f"LLM error: {e}")
        try:
            s = get_kb().stats()
            st.success(f"KB: {s['documents']} docs / {s['chunks']} chunks")
        except Exception as e:  # noqa: BLE001
            st.error(f"KB error: {e}")

    try:
        s = get_kb().stats()
        st.caption(f"📚 Knowledge base: {s['documents']} solutions, {s['chunks']} chunks")
    except Exception:  # noqa: BLE001
        st.caption("📚 Knowledge base: not connected — run docker compose + scripts/init_db.py")


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("🤖 Toni & Sheriff")
st.caption(
    "Two agents debate your request — **Toni** proposes, **Sheriff** challenges — "
    "then consolidate a decision that is stored as RAG knowledge for next time."
)


def reset_task():
    for key in ("controller", "final_ready", "saved"):
        st.session_state.pop(key, None)


# --------------------------------------------------------------------------
# New task entry
# --------------------------------------------------------------------------
if "controller" not in st.session_state:
    request = st.chat_input("Describe your request or problem…")
    if request:
        try:
            provider = build_provider(provider_name, model, api_key)
            kb = get_kb()
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not start: {e}")
            st.stop()
        controller = DebateController(
            provider=provider, kb=kb, request=request, max_rounds=max_rounds
        )
        with st.spinner("Retrieving accumulated knowledge…"):
            controller.start(rerank=rerank)
        st.session_state.controller = controller
        st.session_state.pop("final_ready", None)
        st.session_state.pop("saved", None)
        st.rerun()
    st.info("👆 Enter a request to begin. Past solutions are retrieved automatically.")
    st.stop()


# --------------------------------------------------------------------------
# Active debate
# --------------------------------------------------------------------------
ctrl: DebateController = st.session_state.controller

top = st.container()
with top:
    st.markdown(f"**Request:** {ctrl.request}")
    cols = st.columns([1, 1, 1, 1])
    cols[0].metric("Round", f"{ctrl.round}/{ctrl.max_rounds}")
    cols[1].metric("Status", ctrl.status)
    cols[2].metric("Backend", ctrl.provider.name)
    if cols[3].button("🔄 New task"):
        reset_task()
        st.rerun()

# Retrieved knowledge
with st.expander(f"📚 Accumulated knowledge used ({len(ctrl.retrieved)} chunks)",
                 expanded=not ctrl.transcript):
    if not ctrl.retrieved:
        st.write("No prior knowledge yet — this is a fresh topic.")
    for i, r in enumerate(ctrl.retrieved, 1):
        meta = r.get("metadata") or {}
        score = r.get("rerank_score", r.get("rrf_score", 0))
        st.markdown(f"**K{i}** · _{meta.get('request', r.get('doc_id',''))}_ · score `{score:.4f}`")
        st.caption(r["content"][:500] + ("…" if len(r["content"]) > 500 else ""))

st.divider()

# Render the transcript accumulated so far
for t in ctrl.transcript:
    with st.chat_message(t.agent, avatar=AVATARS[t.agent]):
        label = {"toni": "Toni (architect)", "sheriff": "Sheriff (critic)",
                 "final": "Consolidated decision"}[t.agent]
        st.markdown(f"**{label}** · round {t.round}")
        st.markdown(t.content)
        if t.verdict:
            (st.success if t.verdict == "APPROVE" else st.warning)(f"VERDICT: {t.verdict}")


# --------------------------------------------------------------------------
# Controls / next step
# --------------------------------------------------------------------------
if ctrl.status in ("toni", "sheriff"):
    note = st.text_area(
        "💬 Optional guidance to inject into this round",
        key=f"note_{ctrl.round}",
        placeholder="e.g. 'Prioritise low cost' or 'Must run fully offline'…",
    )
    if st.button(f"▶ Run round {ctrl.round}  (Toni → Sheriff)", type="primary"):
        try:
            with st.chat_message("toni", avatar=AVATARS["toni"]):
                st.markdown(f"**Toni (architect)** · round {ctrl.round}")
                st.write_stream(ctrl.toni_turn(user_note=note))
            with st.chat_message("sheriff", avatar=AVATARS["sheriff"]):
                st.markdown(f"**Sheriff (critic)** · round {ctrl.round}")
                st.write_stream(ctrl.sheriff_turn(user_note=note))
        except Exception as e:  # noqa: BLE001
            st.error(f"LLM error during debate: {e}")
            st.stop()
        st.rerun()

elif ctrl.status == "done" and not ctrl.final_decision:
    last = ctrl.transcript[-1] if ctrl.transcript else None
    if last and last.verdict == "APPROVE":
        st.success("Sheriff approved the proposal. Ready to consolidate.")
    else:
        st.info("Reached the round limit. Consolidate the best agreed solution.")
    if st.button("🤝 Consolidate final decision", type="primary"):
        try:
            with st.chat_message("final", avatar=AVATARS["final"]):
                st.markdown("**Consolidated decision**")
                st.write_stream(ctrl.consolidate())
        except Exception as e:  # noqa: BLE001
            st.error(f"LLM error during consolidation: {e}")
            st.stop()
        st.rerun()

elif ctrl.final_decision:
    st.divider()
    if st.session_state.get("saved"):
        st.success("✅ Solution accumulated into the knowledge base — it will inform future tasks.")
        if st.button("🔄 Start a new task", type="primary"):
            reset_task()
            st.rerun()
    else:
        st.markdown("### Accumulate this solution?")
        st.caption("Stores the consolidated decision as reusable RAG knowledge.")
        c1, c2 = st.columns(2)
        if c1.button("💾 Save to knowledge base", type="primary"):
            with st.spinner("Embedding & storing…"):
                res = ctrl.save_to_knowledge()
            st.session_state.saved = True
            get_kb.clear()  # refresh cached stats
            st.toast(f"Stored {res['chunks']} chunks (doc {res['doc_id'][:8]}…)")
            st.rerun()
        if c2.button("🚮 Discard & new task"):
            reset_task()
            st.rerun()
