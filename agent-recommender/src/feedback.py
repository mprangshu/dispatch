"""User feedback store — thumbs-up / thumbs-down on chatbot replies.

A deliberately simple, file-based store: every rating is appended as one JSON
object per line to ``logs/feedback.jsonl`` (the same gitignored ``logs/`` the
pipeline trace uses). No database — this mirrors the project's "ChromaDB is the
only datastore; everything else stays a plain file" stance and keeps the feedback
loop dependency-free and inspectable.

Public surface:

* ``save_feedback(entry)`` — append one ``FeedbackEntry``.
* ``load_feedback()``      — read every entry back (``[]`` if none yet).
* ``feedback_summary()``   — counts + positive %% + the 5 most recent entries.

The store path is the module-level ``FEEDBACK_FILE`` so tests can point it at a
temp dir (monkeypatch) and never touch the real ``logs/``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .logger import get_logger

log = get_logger(__name__)

# One JSON object per line. Overridable in tests (monkeypatch this attribute).
FEEDBACK_FILE = Path(__file__).resolve().parent.parent / "logs" / "feedback.jsonl"

# The only two ratings the UI can submit.
VALID_RATINGS = ("positive", "negative")


@dataclass
class FeedbackEntry:
    """One rating a user gave a reply."""

    timestamp: str            # ISO 8601, e.g. "2026-06-23T10:15:00+00:00"
    message: str              # the user's original query
    reply: str                # the bot's reply they rated
    rating: str               # "positive" | "negative"
    intent: str | None = None  # recommend | info | clarify, if known


def now_iso() -> str:
    """Current UTC time as an ISO 8601 string (used when recording feedback)."""
    return datetime.now(timezone.utc).isoformat()


def save_feedback(entry: FeedbackEntry) -> None:
    """Append ``entry`` to the feedback log, creating ``logs/`` if needed."""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
    # Log the rating/intent (never the full reply text) so the trace stays terse.
    log.info("FEEDBACK SAVED: rating=%s intent=%s", entry.rating, entry.intent)


def load_feedback() -> list[FeedbackEntry]:
    """Return every stored ``FeedbackEntry`` (``[]`` if the file doesn't exist)."""
    if not FEEDBACK_FILE.exists():
        return []
    entries: list[FeedbackEntry] = []
    for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:  # skip a corrupt line rather than crash
            log.debug("FEEDBACK SKIP: unparseable line")
            continue
        entries.append(
            FeedbackEntry(
                timestamp=str(data.get("timestamp", "")),
                message=str(data.get("message", "")),
                reply=str(data.get("reply", "")),
                rating=str(data.get("rating", "")),
                intent=data.get("intent"),
            )
        )
    return entries


def feedback_summary() -> dict:
    """Aggregate the feedback store into counts, a positive %, and recent entries."""
    entries = load_feedback()
    total = len(entries)
    positive = sum(1 for e in entries if e.rating == "positive")
    negative = sum(1 for e in entries if e.rating == "negative")
    positive_pct = round(positive / total * 100, 1) if total else 0.0
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "positive_pct": positive_pct,
        "recent": entries[-5:],  # last 5, oldest-first within the window
    }