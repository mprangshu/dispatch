"""Phase 6 — "see it for ourselves" LLM verification (manual, hits the real API).

Runs the same handful of queries through the chatbot twice — once with the LLM
**on** (``use_llm=True``) and once **off** (``use_llm=False``) — and prints them
side by side. The point (PROJECT_HANDOFF_v2.md section 7):

    The facts and the grounding verdict must be IDENTICAL in both runs;
    only the prose should get richer with the LLM on.

In particular the ``TBD`` query must say it doesn't have the information in
*both* columns — the grounding gate holds whether or not the LLM is active.

Usage (from ``agent-recommender/`` with the venv active and the store built):

    python app.py index          # if .chroma/ isn't built yet
    python scripts/verify_llm.py

With no ``GEMINI_API_KEY`` set, the LLM-on column simply matches LLM-off (every
call falls back deterministically) — which is itself a valid, safe result. Set
the key in ``.env`` to see the richer LLM-written prose.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `import src` work regardless of the current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, index, llm  # noqa: E402
from src.chatbot import handle  # noqa: E402

# (label, query) — one per intent/grounding case from the handoff runbook.
QUERIES = [
    ("recommendation", "I need to automate UI tests from a live URL"),
    ("info (real content)", "What are the inputs to Test Data Provisioning?"),
    ("info (TBD / missing)", "What hardware does the User Story Analyser need?"),
]

_RULE = "=" * 78


def _store_ready() -> bool:
    """True when both Chroma collections exist (the catalog has been indexed)."""
    try:
        client = index.get_client()
        index.get_summary_collection(client)
        index.get_section_collection(client)
        return True
    except Exception:
        return False


def _print_block(title: str, body: str) -> None:
    print(f"\n--- {title} ---")
    print(body.strip() or "(empty)")


def main() -> int:
    if not _store_ready():
        print(
            "The catalog isn't indexed yet. Build it first with:\n"
            "    python app.py index",
            file=sys.stderr,
        )
        return 1

    key_state = "PRESENT" if llm.available() else "ABSENT"
    print(_RULE)
    print("LLM verification — chatbot replies with the LLM ON vs OFF")
    print(f"GEMINI_API_KEY: {key_state}   (model: {config.MODEL})")
    if not llm.available():
        print(
            "NOTE: no key set, so the LLM-ON column falls back to the deterministic\n"
            "      path and will match LLM-OFF. Set GEMINI_API_KEY in .env to see\n"
            "      the richer LLM-written prose."
        )
    print(_RULE)

    for label, query in QUERIES:
        print(f"\n{_RULE}\n[{label}]  {query}\n{_RULE}")
        on = handle(query, use_llm=True)
        off = handle(query, use_llm=False)
        _print_block("LLM ON  (use_llm=True)", on)
        _print_block("LLM OFF (use_llm=False)", off)
        verdict = "identical" if on.strip() == off.strip() else "different prose"
        print(f"\n[diff] LLM-on vs LLM-off: {verdict}")

    print(f"\n{_RULE}")
    print(
        "Check: facts and grounding (esp. the TBD 'I don't have that') must match\n"
        "across both columns; with a key, only the wording should be richer."
    )
    print(_RULE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
