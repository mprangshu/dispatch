"""Tests for the feedback store (src/feedback.py) and the /feedback endpoints.

Everything runs offline. The feedback file is redirected to a temp path via
``monkeypatch`` so the real ``logs/feedback.jsonl`` is never touched, and the
``logs/`` dir is intentionally absent at the start so directory creation is
exercised.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import src.feedback as feedback
from api import app
from src.feedback import (
    FeedbackEntry,
    feedback_summary,
    load_feedback,
    now_iso,
    save_feedback,
)

client = TestClient(app)


@pytest.fixture
def temp_feedback(tmp_path, monkeypatch):
    """Point the store at a temp file whose parent ``logs/`` does NOT exist yet."""
    path = tmp_path / "logs" / "feedback.jsonl"
    monkeypatch.setattr(feedback, "FEEDBACK_FILE", path)
    return path


def _entry(rating: str, message: str = "q", reply: str = "r", intent: str | None = "info") -> FeedbackEntry:
    return FeedbackEntry(timestamp=now_iso(), message=message, reply=reply, rating=rating, intent=intent)


# ---------------------------------------------------------------------------
# save / load
# ---------------------------------------------------------------------------


def test_save_then_load_roundtrip(temp_feedback):
    save_feedback(_entry("positive", message="What are the inputs?", reply="User Story ID…", intent="info"))
    loaded = load_feedback()
    assert len(loaded) == 1
    e = loaded[0]
    assert e.rating == "positive"
    assert e.message == "What are the inputs?"
    assert e.reply == "User Story ID…"
    assert e.intent == "info"
    assert e.timestamp  # non-empty ISO timestamp


def test_save_creates_missing_logs_dir(temp_feedback):
    assert not temp_feedback.parent.exists()  # logs/ absent before saving
    save_feedback(_entry("negative"))
    assert temp_feedback.exists()
    assert temp_feedback.parent.is_dir()


def test_load_returns_empty_when_no_file(temp_feedback):
    assert load_feedback() == []


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


def test_summary_counts_positive_and_negative(temp_feedback):
    for rating in ["positive", "positive", "positive", "negative"]:
        save_feedback(_entry(rating))
    summary = feedback_summary()
    assert summary["total"] == 4
    assert summary["positive"] == 3
    assert summary["negative"] == 1
    assert summary["positive_pct"] == 75.0
    assert len(summary["recent"]) == 4


def test_summary_recent_is_capped_at_five(temp_feedback):
    for i in range(7):
        save_feedback(_entry("positive", message=f"q{i}"))
    summary = feedback_summary()
    assert summary["total"] == 7
    assert len(summary["recent"]) == 5
    assert summary["recent"][-1].message == "q6"  # newest entry is in the window


def test_summary_empty_store(temp_feedback):
    summary = feedback_summary()
    assert summary == {"total": 0, "positive": 0, "negative": 0, "positive_pct": 0.0, "recent": []}


# ---------------------------------------------------------------------------
# API endpoints (TestClient, no UI)
# ---------------------------------------------------------------------------


def test_post_feedback_returns_saved_true(temp_feedback):
    resp = client.post(
        "/feedback",
        json={"message": "q", "reply": "a", "rating": "positive", "intent": "recommend"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"saved": True}
    # It actually landed in the store.
    assert len(load_feedback()) == 1


def test_summary_endpoint_reflects_saved_entries(temp_feedback):
    client.post("/feedback", json={"message": "good q", "reply": "a", "rating": "positive", "intent": "info"})
    client.post("/feedback", json={"message": "bad q", "reply": "b", "rating": "negative", "intent": "info"})

    resp = client.get("/feedback/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["positive"] == 1
    assert body["negative"] == 1
    assert body["positive_pct"] == 50.0
    messages = [e["message"] for e in body["recent"]]
    assert "good q" in messages and "bad q" in messages
