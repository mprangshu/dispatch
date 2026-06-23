"""Thin HTTP client for the Agent Recommender FastAPI backend.

Phase 8 frontend (PROJECT_HANDOFF_v2.md section 9). This module is the *only*
place that talks to the backend over HTTP — the Streamlit app imports these
functions and never touches ``src`` or ``requests`` directly. Keeping all I/O
here means the client can be unit-tested by mocking ``requests`` without a live
server or a running Streamlit session.

The backend (verified against ``api.py``):

* ``POST /chat``   body ``{"message": str, "use_llm": bool}`` -> ``{"reply": str}``
* ``GET  /agents`` -> ``[{agent_id, name, domain, autonomy_default, tags}]``
* ``GET  /health`` -> ``{"status": str, "llm_available": bool}``

Every call returns an ``ApiResult`` rather than raising: ``ok`` says whether the
request succeeded, ``data`` carries the parsed payload on success, and ``error``
carries a user-facing message on failure. The UI renders ``error`` via
``st.error`` and keeps running, so an unreachable or erroring backend never
crashes the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_BASE_URL = "http://localhost:8000"

# Connect fast, but allow a long read: the backend's first call can be slow
# while Chroma loads its embedding model, and a live LLM reply can take seconds.
HEALTH_TIMEOUT = (5, 10)   # (connect, read) seconds — health/agents are cheap
AGENTS_TIMEOUT = (5, 15)
CHAT_TIMEOUT = (5, 120)    # a cold start + live LLM reply needs headroom
FEEDBACK_TIMEOUT = (5, 15)  # feedback writes/reads are cheap


@dataclass
class ApiResult:
    """Outcome of an HTTP call. ``data`` on success, ``error`` (str) on failure."""

    ok: bool
    data: Any = None
    error: str | None = None


def _unreachable_msg(base_url: str) -> str:
    return (
        f"Backend not reachable at {base_url} — start it from agent-recommender/ with:\n"
        "    uvicorn api:app --port 8000"
    )


def _bad_status_msg(method: str, url: str, resp: requests.Response) -> str:
    body = (resp.text or "").strip()
    if len(body) > 300:
        body = body[:300] + "…"
    detail = f"\n{body}" if body else ""
    return f"{method} {url} failed (HTTP {resp.status_code}).{detail}"


def _normalize(base_url: str | None) -> str:
    return (base_url or DEFAULT_BASE_URL).rstrip("/")


def check_health(base_url: str = DEFAULT_BASE_URL) -> ApiResult:
    """GET /health -> ApiResult(data={"status", "llm_available"})."""
    base = _normalize(base_url)
    url = f"{base}/health"
    try:
        resp = requests.get(url, timeout=HEALTH_TIMEOUT)
    except requests.exceptions.RequestException:
        return ApiResult(ok=False, error=_unreachable_msg(base))
    if resp.status_code != 200:
        return ApiResult(ok=False, error=_bad_status_msg("GET", url, resp))
    try:
        return ApiResult(ok=True, data=resp.json())
    except ValueError:
        return ApiResult(ok=False, error=f"GET {url} returned invalid JSON.")


def fetch_agents(base_url: str = DEFAULT_BASE_URL) -> ApiResult:
    """GET /agents -> ApiResult(data=[{agent_id, name, domain, ...}, ...])."""
    base = _normalize(base_url)
    url = f"{base}/agents"
    try:
        resp = requests.get(url, timeout=AGENTS_TIMEOUT)
    except requests.exceptions.RequestException:
        return ApiResult(ok=False, error=_unreachable_msg(base))
    if resp.status_code != 200:
        return ApiResult(ok=False, error=_bad_status_msg("GET", url, resp))
    try:
        return ApiResult(ok=True, data=resp.json())
    except ValueError:
        return ApiResult(ok=False, error=f"GET {url} returned invalid JSON.")


def call_chat(
    message: str,
    *,
    use_llm: bool = True,
    base_url: str = DEFAULT_BASE_URL,
) -> ApiResult:
    """POST /chat with {message, use_llm} -> ApiResult(data=reply_string)."""
    base = _normalize(base_url)
    url = f"{base}/chat"
    try:
        resp = requests.post(
            url,
            json={"message": message, "use_llm": use_llm},
            timeout=CHAT_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return ApiResult(ok=False, error=_unreachable_msg(base))
    if resp.status_code != 200:
        return ApiResult(ok=False, error=_bad_status_msg("POST", url, resp))
    try:
        payload = resp.json()
    except ValueError:
        return ApiResult(ok=False, error=f"POST {url} returned invalid JSON.")
    return ApiResult(ok=True, data=payload.get("reply", ""))


def submit_feedback(
    message: str,
    reply: str,
    rating: str,
    *,
    intent: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
) -> ApiResult:
    """POST /feedback with the rating -> ApiResult(data={"saved": true})."""
    base = _normalize(base_url)
    url = f"{base}/feedback"
    try:
        resp = requests.post(
            url,
            json={"message": message, "reply": reply, "rating": rating, "intent": intent},
            timeout=FEEDBACK_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return ApiResult(ok=False, error=_unreachable_msg(base))
    if resp.status_code != 200:
        return ApiResult(ok=False, error=_bad_status_msg("POST", url, resp))
    try:
        return ApiResult(ok=True, data=resp.json())
    except ValueError:
        return ApiResult(ok=False, error=f"POST {url} returned invalid JSON.")


def fetch_feedback_summary(base_url: str = DEFAULT_BASE_URL) -> ApiResult:
    """GET /feedback/summary -> ApiResult(data={total, positive, negative, ...})."""
    base = _normalize(base_url)
    url = f"{base}/feedback/summary"
    try:
        resp = requests.get(url, timeout=FEEDBACK_TIMEOUT)
    except requests.exceptions.RequestException:
        return ApiResult(ok=False, error=_unreachable_msg(base))
    if resp.status_code != 200:
        return ApiResult(ok=False, error=_bad_status_msg("GET", url, resp))
    try:
        return ApiResult(ok=True, data=resp.json())
    except ValueError:
        return ApiResult(ok=False, error=f"GET {url} returned invalid JSON.")
