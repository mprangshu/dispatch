"""Tests for the FastAPI backend (Phase 7, PROJECT_HANDOFF_v2.md section 8).

Uses FastAPI's ``TestClient`` and ``use_llm=False`` so the endpoints are
exercised deterministically with no network/LLM. ``/chat`` queries that hit
retrieval run against a real Chroma store built from the actual catalog into a
temp dir (the store is restored afterward, like the chatbot tests).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import src.feedback as feedback
from api import app
from src import config, handle, index, llm
from src.loader import load_agents

client = TestClient(app)


@pytest.fixture(scope="module")
def built_store(tmp_path_factory):
    """Index the real catalog into a temp Chroma path and point config at it."""
    chroma_path = tmp_path_factory.mktemp("chroma_api")
    original = config.CHROMA_PATH
    config.CHROMA_PATH = chroma_path
    index.build_index(chroma_path=chroma_path)
    yield
    config.CHROMA_PATH = original


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_reports_ok_and_llm_flag():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    # Reflects the real key state (no key in CI -> False); just must match llm.
    assert isinstance(body["llm_available"], bool)
    assert body["llm_available"] == llm.available()


# ---------------------------------------------------------------------------
# /agents
# ---------------------------------------------------------------------------


def test_agents_lists_the_live_catalog():
    res = client.get("/agents")
    assert res.status_code == 200
    body = res.json()

    # Reflects whatever is in agents/ — never hard-coded to a fixed count.
    expected = load_agents(config.AGENTS_DIR)
    assert len(body) == len(expected)
    assert {a["agent_id"] for a in body} == {a.agent_id for a in expected}

    # Each record carries the agreed fields with the right shapes.
    first = body[0]
    assert set(first) == {"agent_id", "name", "domain", "autonomy_default", "tags"}
    assert isinstance(first["tags"], list)


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------


def test_chat_recommendation_matches_handle(built_store):
    message = "I need to automate UI tests from a live URL"
    res = client.post("/chat", json={"message": message, "use_llm": False})
    assert res.status_code == 200
    reply = res.json()["reply"]
    assert "Test Script Generator" in reply
    # The API is a thin pass-through: identical to calling handle() directly.
    assert reply == handle(message, use_llm=False)


def test_chat_vague_message_clarifies_without_store():
    # A vague message classifies as clarify before any retrieval — no store needed.
    res = client.post("/chat", json={"message": "hi", "use_llm": False})
    assert res.status_code == 200
    low = res.json()["reply"].lower()
    assert "not sure" in low or "describe a task" in low


def test_chat_use_llm_defaults_to_true():
    # Omitting use_llm should default to True per the request model.
    res = client.post("/chat", json={"message": "hi"})
    assert res.status_code == 200
    assert "reply" in res.json()


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# /feedback  and  /feedback/summary
# ---------------------------------------------------------------------------


def test_feedback_post_then_summary(tmp_path, monkeypatch):
    # Redirect the store to a temp file so the real logs/ is untouched.
    monkeypatch.setattr(feedback, "FEEDBACK_FILE", tmp_path / "logs" / "feedback.jsonl")

    saved = client.post(
        "/feedback",
        json={"message": "Was this useful?", "reply": "Here you go.",
              "rating": "positive", "intent": "recommend"},
    )
    assert saved.status_code == 200
    assert saved.json() == {"saved": True}

    summary = client.get("/feedback/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == 1
    assert body["positive"] == 1
    assert body["negative"] == 0
    assert body["positive_pct"] == 100.0
    assert body["recent"][0]["message"] == "Was this useful?"
    assert body["recent"][0]["rating"] == "positive"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_header_present_for_cross_origin_request():
    res = client.get("/health", headers={"Origin": "http://example.com"})
    assert res.status_code == 200
    # With credentials allowed, Starlette echoes the request origin rather than
    # returning a literal "*" (CORS forbids "*" + credentials); both mean the
    # cross-origin request is permitted.
    allow_origin = res.headers.get("access-control-allow-origin")
    assert allow_origin in ("*", "http://example.com")
