"""Tests for the structured logging / tracing layer (src/logger.py).

These assert that handling a message emits the step-by-step trace a manager
relies on, that the grounding verdict is logged honestly, and — the safety
check — that no secret is ever logged. They run offline: the info LLM call is
monkeypatched (so no key/network) and the rest use the deterministic path.

Captured via pytest's ``caplog``; our loggers live under ``agent_chatbot`` and
propagate to the root, so caplog sees every record.
"""

from __future__ import annotations

import logging

import pytest

import src.info as info
import src.recommender as recommender
from src import config, index
from src.chatbot import handle


@pytest.fixture(scope="module")
def built_store(tmp_path_factory):
    """Index the real catalog into a temp Chroma path and point config at it."""
    chroma_path = tmp_path_factory.mktemp("chroma_log")
    original = config.CHROMA_PATH
    config.CHROMA_PATH = chroma_path
    index.build_index(chroma_path=chroma_path)
    yield
    config.CHROMA_PATH = original


def _all_messages(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


def test_info_query_logs_full_trace(built_store, caplog, monkeypatch):
    # Drive the LLM branch deterministically (no key/network) so the prompt is
    # actually built and logged.
    monkeypatch.setattr(
        info, "generate",
        lambda *a, **k: "The inputs are User Story ID, Autonomy level, and User confirmations.",
    )

    with caplog.at_level(logging.DEBUG, logger="agent_chatbot"):
        handle("What are the inputs to Test Data Provisioning?", use_llm=True)

    text = _all_messages(caplog)
    assert "INTENT DETECTED" in text
    assert "AGENT IDENTIFIED" in text
    assert "PROMPT SENT TO LLM" in text
    assert "GROUNDING CHECK" in text
    # The exact prompt (which the manager wants) made it into the log.
    assert "Documentation excerpts:" in text


def test_tbd_query_logs_grounding_false(caplog):
    # Exercise the grounding gate against a stubbed TBD section, so the test is
    # robust to which catalog fields happen to be filled in. The gate must fire
    # and log GROUNDING CHECK: False (and never reach the LLM).
    from src.retriever import Hit

    tbd_hit = Hit(
        agent_id="user-story-analyser",
        name="User Story Analyser Agent",
        text="User Story Analyser Agent — Deployment\n\n**Hardware:** TBD\n**Software:** TBD",
        score=0.7,
        section="Deployment",
        metadata={
            "agent_id": "user-story-analyser",
            "name": "User Story Analyser Agent",
            "section": "Deployment",
        },
    )

    with caplog.at_level(logging.DEBUG, logger="agent_chatbot"):
        result = info.answer_question(
            "What hardware does the User Story Analyser need?",
            use_llm=False,
            search_fn=lambda *a, **k: [tbd_hit],
        )

    assert result["grounded"] is False
    assert "GROUNDING CHECK: False" in _all_messages(caplog)


def test_no_log_record_contains_a_secret(built_store, caplog, monkeypatch):
    # Exercise both paths with the LLM branch taken, fully offline.
    monkeypatch.setattr(info, "generate", lambda *a, **k: "canned grounded answer")
    monkeypatch.setattr(recommender, "generate", lambda *a, **k: "canned recommendation")

    with caplog.at_level(logging.DEBUG, logger="agent_chatbot"):
        handle("What are the inputs to Test Data Provisioning?", use_llm=True)
        handle("I need to automate UI tests from a live URL", use_llm=True)

    for record in caplog.records:
        message = record.getMessage()
        assert "GEMINI_API_KEY" not in message
        assert "API_KEY" not in message
