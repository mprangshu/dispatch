"""LLM client wrapper — a thin, swappable layer over the configured model.

Centralizes access to the LLM (Google Gemini by default, see ``config.MODEL``)
so the rest of the package never imports the SDK directly and the model is
swappable in one place. The API key is read from the environment / ``.env``
(``GEMINI_API_KEY``).

``generate()`` is deliberately fault-tolerant: it returns ``None`` when the LLM
is unavailable (no key, SDK missing) or the call fails, so every caller can fall
back to a deterministic, offline code path rather than crash. This keeps the
recommendation/info features usable — and their tests runnable — without network
access (PROBLEM_STATEMENT.md section 2: the LLM is configurable).
"""

from __future__ import annotations

import os

from . import config
from .logger import get_logger

log = get_logger(__name__)

# Inject the Windows certificate store so httpx trusts the Cognizant Zscaler
# proxy CA without needing SSL_CERT_FILE or a custom CA bundle.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# Load .env so GEMINI_API_KEY is available without exporting it manually.
try:  # python-dotenv is a declared dependency, but don't hard-fail without it.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - only hit if python-dotenv is absent
    pass

_client = None  # lazily constructed Gemini client, cached across calls


def available() -> bool:
    """True when an API key is configured (so an LLM call could succeed)."""
    return bool(os.getenv("GEMINI_API_KEY"))


def _client_or_none():
    """Return a cached Gemini client, or ``None`` if one can't be built."""
    global _client
    if _client is not None:
        return _client
    if not available():
        return None
    try:
        from google import genai

        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    except Exception:  # pragma: no cover - SDK/auth issues -> fall back
        return None
    return _client


def generate(prompt: str, system: str | None = None, model: str | None = None) -> str | None:
    """Generate text for ``prompt``; return ``None`` if the LLM is unavailable.

    ``system`` is an optional system instruction; ``model`` overrides
    ``config.MODEL``. Temperature is kept moderate (0.5) for stable, grounded
    output.
    """
    log.debug("LLM CALL: model=%s temperature=0.5", model or config.MODEL)
    if system:
        log.debug("LLM SYSTEM PROMPT: %s", system)
    log.debug("LLM USER PROMPT: %s", prompt)

    client = _client_or_none()
    if client is None:
        log.info("LLM RESULT: None — fallback")
        return None
    try:
        from google.genai import types

        cfg = types.GenerateContentConfig(temperature=0.5)
        if system:
            cfg.system_instruction = system
        response = client.models.generate_content(
            model=model or config.MODEL,
            contents=prompt,
            config=cfg,
        )
        text = (response.text or "").strip()
        log.info("LLM RESULT: %s", text[:150] if text else "None — fallback")
        return text or None
    except Exception:  # pragma: no cover - network/quota/parse errors -> fall back
        log.exception("LLM RESULT: None — fallback (exception below)")
        return None