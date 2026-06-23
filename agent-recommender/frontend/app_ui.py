"""Streamlit chat UI for the Agent Recommender & Q&A Chatbot.

Phase 8 (PROJECT_HANDOFF_v2.md section 9). A thin client that sits OVER the
FastAPI backend in ``api.py`` and talks to it strictly over HTTP via
``api_client`` — it never imports from ``src``, keeping the core
interface-decoupled exactly as PROBLEM_STATEMENT.md section 7 requires.

This module owns only rendering and ``st.session_state``; every network call
goes through ``api_client`` (which fails soft, returning errors the UI shows
instead of crashing). The UI makes no grounding decisions — it renders whatever
``/chat`` returns.

Run (two terminals, from ``agent-recommender/`` with the venv active):

    # terminal 1 — backend
    uvicorn api:app --port 8000
    # terminal 2 — this UI
    cd frontend && streamlit run app_ui.py
"""

from __future__ import annotations

import streamlit as st

import api_client

# Example prompts covering the three behaviors (recommend / info / missing-data).
EXAMPLE_PROMPTS = [
    ("🧭 Recommend", "I need to automate UI tests from a live URL"),
    ("📄 Info lookup", "What are the inputs to Test Data Provisioning?"),
    ("🚫 Missing data", "What hardware does the User Story Analyser need?"),
]


def _init_state() -> None:
    """Seed session state once per session."""
    st.session_state.setdefault("messages", [])  # list of {role, content}
    st.session_state.setdefault("api_base", api_client.DEFAULT_BASE_URL)
    st.session_state.setdefault("use_llm", True)
    st.session_state.setdefault("pending_prompt", None)
    st.session_state.setdefault("agents_cache", {})  # base_url -> agents list
    st.session_state.setdefault("feedback_given", {})  # message index -> rating


def _render_sidebar() -> None:
    """API config, health indicator, agent list, and Clear chat."""
    with st.sidebar:
        st.header("⚙️ Settings")

        st.session_state.api_base = st.text_input(
            "API base URL",
            value=st.session_state.api_base,
            help="Where the FastAPI backend is running.",
        )
        base = st.session_state.api_base

        st.session_state.use_llm = st.toggle(
            "Use LLM for prose",
            value=st.session_state.use_llm,
            help="On: richer LLM-written wording. Off: deterministic, grounded "
            "fallback. Facts and grounding are identical either way.",
        )

        # --- Health indicator -------------------------------------------------
        health = api_client.check_health(base)
        if health.ok:
            llm_on = bool(health.data.get("llm_available"))
            llm_note = "LLM key configured" if llm_on else "no LLM key (deterministic mode)"
            st.success(f"🟢 Backend up · {llm_note}")
        else:
            st.error(f"🔴 Backend down\n\n{health.error}")

        # --- Agent catalog ----------------------------------------------------
        st.subheader("Agents")
        agents_res = api_client.fetch_agents(base)
        if agents_res.ok:
            st.session_state.agents_cache[base] = agents_res.data
            agents = agents_res.data
        else:
            # Fall back to the last good list for this URL, if we have one.
            agents = st.session_state.agents_cache.get(base, [])
            if not agents:
                st.caption("Agent list unavailable while the backend is down.")

        for agent in agents:
            name = agent.get("name", agent.get("agent_id", "?"))
            agent_id = agent.get("agent_id", "")
            st.markdown(f"**{name}**  \n`{agent_id}`")

        # --- Feedback summary (manager view) ----------------------------------
        with st.expander("📊 Feedback", expanded=False):
            summary_res = api_client.fetch_feedback_summary(base)
            if not summary_res.ok:
                st.caption("Feedback summary unavailable while the backend is down.")
            else:
                s = summary_res.data
                total = s.get("total", 0)
                st.markdown(f"**Total ratings:** {total}")
                if total:
                    pos, neg = s.get("positive", 0), s.get("negative", 0)
                    pos_pct = s.get("positive_pct", 0.0)
                    neg_pct = round(100.0 - pos_pct, 1)
                    st.markdown(f"👍 Positive: {pos} ({pos_pct}%)")
                    st.markdown(f"👎 Negative: {neg} ({neg_pct}%)")
                    recent = s.get("recent", [])
                    if recent:
                        rows = [
                            {
                                "timestamp": e.get("timestamp", ""),
                                "message": (e.get("message", "")[:40]),
                                "rating": e.get("rating", ""),
                            }
                            for e in reversed(recent)  # newest first
                        ]
                        st.dataframe(rows, use_container_width=True, hide_index=True)
                else:
                    st.caption("No ratings yet.")

        st.divider()
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_prompt = None
            st.session_state.feedback_given = {}
            st.rerun()


def _render_examples() -> None:
    """Clickable example prompts; sets a pending message and reruns."""
    st.caption("Try an example:")
    cols = st.columns(len(EXAMPLE_PROMPTS))
    for col, (label, prompt) in zip(cols, EXAMPLE_PROMPTS):
        if col.button(label, use_container_width=True, help=prompt):
            st.session_state.pending_prompt = prompt
            st.rerun()


def _send_feedback(idx: int, msg: dict, rating: str) -> None:
    """POST the rating, remember it for this message, and confirm via a toast."""
    res = api_client.submit_feedback(
        msg.get("query", ""),
        msg.get("content", ""),
        rating,
        intent=msg.get("intent"),  # None when the client doesn't know it
        base_url=st.session_state.api_base,
    )
    if res.ok:
        st.session_state.feedback_given[idx] = rating
        st.toast("Thanks for your feedback!", icon="✅")
    else:
        st.toast(f"Couldn't save feedback: {res.error}", icon="⚠️")


def _render_feedback_buttons(idx: int, msg: dict) -> None:
    """Render 👍 / 👎 under one assistant reply; collapse to a note once rated."""
    given = st.session_state.feedback_given.get(idx)
    if given:
        st.caption("✅ Thanks for your feedback!")
        return
    up, down, _ = st.columns([1, 1, 4])
    if up.button("👍 Good answer", key=f"fb_up_{idx}"):
        _send_feedback(idx, msg, "positive")
        st.rerun()  # redraw this message as rated; chat history is preserved
    if down.button("👎 Bad answer", key=f"fb_down_{idx}"):
        _send_feedback(idx, msg, "negative")
        st.rerun()


def _render_history() -> None:
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Only successful assistant replies are rateable (not error markers).
            if msg["role"] == "assistant" and msg.get("feedbackable"):
                _render_feedback_buttons(idx, msg)


def _handle_message(message: str) -> None:
    """Append the user turn, call the backend, and append the reply."""
    st.session_state.messages.append({"role": "user", "content": message})
    with st.chat_message("user"):
        st.markdown(message)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = api_client.call_chat(
                message,
                use_llm=st.session_state.use_llm,
                base_url=st.session_state.api_base,
            )
        if result.ok:
            reply = result.data or "_(empty reply)_"
            st.markdown(reply)
            msg = {
                "role": "assistant",
                "content": reply,
                "query": message,   # remembered so feedback can report the query
                "feedbackable": True,
            }
            st.session_state.messages.append(msg)
            # Show the 👍 / 👎 buttons immediately under the fresh reply.
            _render_feedback_buttons(len(st.session_state.messages) - 1, msg)
        else:
            st.error(result.error)
            # Persist a short marker so the failed turn stays visible in history
            # (not rateable — feedback is for real answers only).
            st.session_state.messages.append(
                {"role": "assistant", "content": f"⚠️ {result.error}"}
            )


def main() -> None:
    st.set_page_config(page_title="Agent Recommender", page_icon="🤖", layout="centered")
    _init_state()

    st.title("🤖 Agent Recommender & Q&A Chatbot")
    st.caption(
        "Describe a task to get an agent recommendation, or ask about a specific "
        "agent. Answers are grounded strictly in the agent catalog."
    )

    _render_sidebar()
    if not st.session_state.messages:
        _render_examples()
    _render_history()

    # An example-button click (pending_prompt) or a typed message both feed here.
    typed = st.chat_input("Ask about an agent, or describe a task…")
    user_message = st.session_state.pending_prompt or typed
    st.session_state.pending_prompt = None

    if user_message:
        _handle_message(user_message)


if __name__ == "__main__":
    main()
