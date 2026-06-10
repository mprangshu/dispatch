"""Tests for the frontend HTTP client (Phase 8).

These exercise ``api_client`` with the network layer mocked (``requests.get`` /
``requests.post`` monkeypatched), so they run with **no live server** and no
Streamlit session. They assert the client handles a normal reply, an
unreachable backend, and a non-200 response by returning an ``ApiResult`` the UI
can render — never by raising.

``api_client`` lives one directory up; we add ``frontend/`` to ``sys.path`` so
this file imports it directly. We deliberately do NOT make ``frontend/tests`` a
package (no ``__init__.py``): the backend already has a ``tests`` package, and a
second one would collide under pytest's import mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # frontend/

import api_client  # noqa: E402


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, status_code=200, json_data=None, text="", raise_json=False):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("no json body")
        return self._json


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------


def test_call_chat_normal_reply(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        assert url == "http://test:8000/chat"
        assert json == {"message": "hello", "use_llm": True}
        return FakeResponse(200, {"reply": "hi there"})

    monkeypatch.setattr(api_client.requests, "post", fake_post)
    res = api_client.call_chat("hello", base_url="http://test:8000")
    assert res.ok is True
    assert res.data == "hi there"
    assert res.error is None


def test_call_chat_passes_use_llm_flag(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured.update(json)
        return FakeResponse(200, {"reply": "ok"})

    monkeypatch.setattr(api_client.requests, "post", fake_post)
    api_client.call_chat("x", use_llm=False, base_url="http://test:8000")
    assert captured["use_llm"] is False


def test_call_chat_api_down_returns_error(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(api_client.requests, "post", fake_post)
    res = api_client.call_chat("hello", base_url="http://localhost:8000")
    assert res.ok is False
    assert res.data is None
    assert "not reachable" in res.error
    assert "uvicorn api:app" in res.error  # tells the user how to start it
    assert "http://localhost:8000" in res.error


def test_call_chat_timeout_treated_as_unreachable(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise requests.exceptions.Timeout("read timed out")

    monkeypatch.setattr(api_client.requests, "post", fake_post)
    res = api_client.call_chat("hello")
    assert res.ok is False
    assert "not reachable" in res.error


def test_call_chat_non_200_returns_error(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return FakeResponse(500, text="internal error")

    monkeypatch.setattr(api_client.requests, "post", fake_post)
    res = api_client.call_chat("hello")
    assert res.ok is False
    assert "500" in res.error
    assert "internal error" in res.error


# ---------------------------------------------------------------------------
# /agents
# ---------------------------------------------------------------------------


def test_fetch_agents_normal(monkeypatch):
    agents = [{"agent_id": "a", "name": "Agent A"}, {"agent_id": "b", "name": "Agent B"}]

    def fake_get(url, timeout=None):
        assert url == "http://test:8000/agents"
        return FakeResponse(200, agents)

    monkeypatch.setattr(api_client.requests, "get", fake_get)
    res = api_client.fetch_agents(base_url="http://test:8000")
    assert res.ok is True
    assert res.data == agents


def test_fetch_agents_api_down(monkeypatch):
    def fake_get(url, timeout=None):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(api_client.requests, "get", fake_get)
    res = api_client.fetch_agents()
    assert res.ok is False
    assert "not reachable" in res.error


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_check_health_normal(monkeypatch):
    def fake_get(url, timeout=None):
        assert url == "http://test:8000/health"
        return FakeResponse(200, {"status": "ok", "llm_available": True})

    monkeypatch.setattr(api_client.requests, "get", fake_get)
    res = api_client.check_health("http://test:8000")
    assert res.ok is True
    assert res.data["status"] == "ok"
    assert res.data["llm_available"] is True


def test_check_health_non_200(monkeypatch):
    def fake_get(url, timeout=None):
        return FakeResponse(503, text="service unavailable")

    monkeypatch.setattr(api_client.requests, "get", fake_get)
    res = api_client.check_health()
    assert res.ok is False
    assert "503" in res.error


def test_check_health_api_down(monkeypatch):
    def fake_get(url, timeout=None):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(api_client.requests, "get", fake_get)
    res = api_client.check_health("http://localhost:8000")
    assert res.ok is False
    assert "not reachable" in res.error


# ---------------------------------------------------------------------------
# URL handling
# ---------------------------------------------------------------------------


def test_base_url_trailing_slash_normalized(monkeypatch):
    seen = {}

    def fake_get(url, timeout=None):
        seen["url"] = url
        return FakeResponse(200, {"status": "ok", "llm_available": False})

    monkeypatch.setattr(api_client.requests, "get", fake_get)
    api_client.check_health("http://test:8000/")
    assert seen["url"] == "http://test:8000/health"
