"""Integration tests for the orchestration layer (Phase 5).

These exercise ``chatbot.handle`` end to end and check the acceptance criteria
in PROBLEM_STATEMENT.md section 9:

* a recommendation query returns the correct agent;
* an info query returns an answer grounded in the right section;
* a missing-data query returns an honest "not available", never a fabrication;
* a vague query triggers a clarifying question;
* adding a new `.md` file and re-indexing makes that agent discoverable with no
  code changes.

The acceptance tests run against a **real** ChromaDB store built from the actual
``agents/`` catalog (so they prove the whole stack works), while a few routing /
formatting edges are checked with **stubbed** path functions so the chatbot's own
logic (no-match listing, source attribution, ambiguous shortlist) is verified
deterministically. ``use_llm=False`` throughout, so nothing makes a network call.
"""

from __future__ import annotations

import shutil

import pytest

from src import chatbot, config, index
from src.chatbot import handle
from src.retriever import Hit, search_agents


@pytest.fixture(scope="module")
def built_store(tmp_path_factory):
    """Index the real catalog into a temp Chroma path and point config at it."""
    chroma_path = tmp_path_factory.mktemp("chroma")
    original = config.CHROMA_PATH
    config.CHROMA_PATH = chroma_path
    index.build_index(chroma_path=chroma_path)
    yield
    config.CHROMA_PATH = original


# ---------------------------------------------------------------------------
# Acceptance criteria — real index (PROBLEM_STATEMENT.md section 9)
# ---------------------------------------------------------------------------


def test_recommendation_returns_correct_agent(built_store):
    reply = handle("I need to automate UI tests from a live URL", use_llm=False)
    assert "Test Script Generator" in reply


def test_info_answer_is_grounded_in_the_right_section(built_store):
    reply = handle("What are the inputs to Test Data Provisioning?", use_llm=False)
    # Drawn verbatim from that agent's Inputs section.
    assert "User Story ID" in reply
    assert "Test Data Provisioning" in reply  # source attribution


def test_deployment_question_is_grounded(built_store):
    # The Deployment fields now carry real (dummy) data, so a hardware question is
    # answered from that section and attributed to it. (The grounding gate that
    # produces an honest "I don't have that" for *empty* sections is still covered
    # by the stub-based tests in test_info.py / test_llm.py, which don't depend on
    # the live catalog content.)
    reply = handle("What hardware does the User Story Analyser need?", use_llm=False)
    assert "vCPU" in reply or "RAM" in reply
    assert "Source:" in reply  # grounded answers carry a source attribution


def test_vague_message_triggers_clarification():
    # No store needed: a vague message classifies as clarify before any retrieval.
    reply = handle("hi", use_llm=False)
    low = reply.lower()
    assert "not sure" in low or "describe a task" in low


def test_new_agent_is_discoverable_after_reindex(tmp_path):
    """Adding a `.md` file + re-indexing surfaces it with no code changes (§9)."""
    # Copy the real catalog into a temp dir and add a fifth, distinctive agent.
    agents_dir = tmp_path / "agents"
    shutil.copytree(config.AGENTS_DIR, agents_dir)
    (agents_dir / "performance-tester.md").write_text(
        "---\n"
        "agent_id: performance-tester\n"
        "name: Performance Tester Agent\n"
        "domain: testing\n"
        "tags: [load-testing, performance, throughput, latency, benchmarking]\n"
        "autonomy_default: L2\n"
        "autonomy_supported: [L1, L2]\n"
        "triggers: [manual]\n"
        "---\n\n"
        "## Overview\n"
        "The Performance Tester runs load and stress tests against an API or web "
        "service, ramping concurrent users to measure throughput, latency, and "
        "error rates under load, then reports where the system degrades.\n",
        encoding="utf-8",
    )

    chroma_path = tmp_path / "chroma"
    original = config.CHROMA_PATH
    config.CHROMA_PATH = chroma_path
    try:
        expected = len(list(agents_dir.glob("*.md")))  # whole catalog + the new one
        stats = index.build_index(agents_dir=agents_dir, chroma_path=chroma_path)
        assert stats["agents"] == expected
        # Discoverable via semantic search with no code change.
        hits = search_agents("run load and performance tests on my API", k=expected)
        assert "performance-tester" in {h.agent_id for h in hits}
    finally:
        config.CHROMA_PATH = original


# ---------------------------------------------------------------------------
# Routing / formatting edges — stubbed paths (deterministic, no store)
# ---------------------------------------------------------------------------


def test_no_match_lists_available_agents(monkeypatch):
    monkeypatch.setattr(chatbot, "detect_intent", lambda q, **k: "recommend")
    monkeypatch.setattr(
        chatbot,
        "recommend",
        lambda q, **k: {"agents": [], "explanation": "I couldn't find a fit.", "ambiguous": False},
    )

    reply = handle("how do I bake a cake", use_llm=False)
    assert "couldn't find a fit" in reply.lower()
    assert "Available agents:" in reply
    # Every catalog agent is offered as an alternative.
    for name in chatbot.available_agent_names():
        assert name in reply


def test_info_reply_attributes_its_source(monkeypatch):
    hit = Hit(
        agent_id="test-data-provisioning",
        name="Test Data Provisioning",
        text="...",
        score=0.7,
        section="Outputs",
        metadata={},
    )
    monkeypatch.setattr(chatbot, "detect_intent", lambda q, **k: "info")
    monkeypatch.setattr(
        chatbot,
        "answer_question",
        lambda q, **k: {"answer": "It exports a CSV or JSON dataset.", "sources": [hit], "grounded": True},
    )

    reply = handle("what does test data provisioning output", use_llm=False)
    assert "CSV or JSON" in reply
    assert "Source: Test Data Provisioning — Outputs" in reply


def test_ungrounded_info_reply_has_no_source_line(monkeypatch):
    monkeypatch.setattr(chatbot, "detect_intent", lambda q, **k: "info")
    monkeypatch.setattr(
        chatbot,
        "answer_question",
        lambda q, **k: {"answer": "I don't have that information.", "sources": [], "grounded": False},
    )

    reply = handle("what hardware does it need", use_llm=False)
    assert "Source:" not in reply
    assert "don't have" in reply.lower()


def test_ambiguous_shortlist_is_surfaced(monkeypatch):
    monkeypatch.setattr(chatbot, "detect_intent", lambda q, **k: "recommend")
    monkeypatch.setattr(
        chatbot,
        "recommend",
        lambda q, **k: {
            "agents": [object(), object()],
            "explanation": "A few agents could fit:\n- Agent A\n- Agent B",
            "ambiguous": True,
        },
    )

    reply = handle("help me with testing", use_llm=False)
    assert "Agent A" in reply and "Agent B" in reply
