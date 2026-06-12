"""Structured logging & tracing for the whole pipeline.

One call — :func:`get_logger` — returns a logger wired to two handlers that are
configured exactly once per process:

* **Console** (stdout), INFO and above, human-readable: ``[STEP] <message>`` — the
  step-by-step trace a manager watches live.
* **File** (``logs/agent_chatbot.log``), DEBUG and above, with timestamp, module,
  and level: ``2024-01-01 12:00:00 | MODULE | LEVEL | message`` — the full record,
  including the DEBUG detail (retrieved chunk text, queries) that's too verbose for
  the console. ``logs/`` is created if it doesn't exist.

All pipeline loggers live under the ``agent_chatbot`` base, so configuration is
isolated to this package; records still **propagate** to the root logger, so
pytest's ``caplog`` (and any host application's logging) can observe them.

Sensitive-data rule: this module never logs secrets. The API key is never passed
to a logger — only prompt / answer / agent text flows through here. Full prompt
text is logged at INFO (the manager wants to see it); full chunk text at DEBUG.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

BASE_NAME = "agent_chatbot"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "agent_chatbot.log"

_CONSOLE_FORMAT = "[STEP] %(message)s"
_FILE_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _configure_base() -> logging.Logger:
    """Attach the console + file handlers to the base logger, once."""
    base = logging.getLogger(BASE_NAME)
    if getattr(base, "_pipeline_configured", False):
        return base

    base.setLevel(logging.DEBUG)
    # Keep propagation on so pytest's caplog / a host app's root logger can see
    # records; the base handlers below are what actually render them.
    base.propagate = True

    # Degrade unencodable glyphs (e.g. the box-drawing rules below) to "?" on a
    # non-UTF-8 console (Windows cp1252) instead of raising UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    base.addHandler(console)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_FILE_DATEFMT))
        base.addHandler(file_handler)
    except OSError:  # pragma: no cover - e.g. read-only fs; console still works
        pass

    base._pipeline_configured = True
    return base


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured logger for ``name`` (call as ``get_logger(__name__)``).

    All returned loggers are children of the ``agent_chatbot`` base, which carries
    the console + file handlers (set up once on first call).
    """
    _configure_base()
    if not name:
        return logging.getLogger(BASE_NAME)
    return logging.getLogger(f"{BASE_NAME}.{name}")
