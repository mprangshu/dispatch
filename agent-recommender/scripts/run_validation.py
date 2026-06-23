"""Validation harness — score the chatbot against a fixed Q&A set.

Runs every case in ``tests/validation_set.json`` through ``handle(..., use_llm=False)``
(offline, no API key) and prints a pass/fail report with an overall score. This
is the manager-facing quality gate: a silent regression from a catalog edit, a
threshold change, or an embedding-model swap shows up here as a dropped score.

Scoring per case:
  * PASS if EVERY ``expected_keywords`` entry appears in the reply (case-insensitive).
  * For cases with a non-null ``should_be_grounded``, the grounded verdict from
    ``answer_question(query, use_llm=False)["grounded"]`` must also match.

Exit code: 0 if all cases pass, 1 otherwise (so CI can gate on it).

Usage (from agent-recommender/, venv active):
    python scripts/run_validation.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Make the package importable when run as a plain script (python scripts/...).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import config, index  # noqa: E402
from src.chatbot import handle  # noqa: E402
from src.info import answer_question  # noqa: E402

VALIDATION_SET = _ROOT / "tests" / "validation_set.json"
_RULE = "═" * 60


def _quiet_console() -> None:
    """Raise the console handler to WARNING so the report isn't buried under the
    pipeline's ``[STEP]`` trace. The file handler keeps the full record in
    logs/agent_chatbot.log."""
    base = logging.getLogger("agent_chatbot")
    for handler in base.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.WARNING)


def _load_cases() -> list[dict]:
    return json.loads(VALIDATION_SET.read_text(encoding="utf-8"))


def _ensure_index() -> None:
    """Build the ChromaDB store if it doesn't exist yet (idempotent)."""
    if not Path(config.CHROMA_PATH).exists():
        print(f"[setup] No store at {config.CHROMA_PATH} — building index...")
        stats = index.build_index()
        print(f"[setup] Indexed {stats['agents']} agents.\n")


def _score_case(case: dict) -> tuple[bool, str, dict]:
    """Run one case; return (passed, reply, detail)."""
    query = case["query"]
    reply = handle(query, use_llm=False)
    low = reply.lower()

    detail: dict = {}

    # 1) All expected keywords must be present (case-insensitive).
    missing = [kw for kw in case.get("expected_keywords", []) if kw.lower() not in low]
    keywords_ok = not missing
    detail["missing_keywords"] = missing

    # 2) Grounded verdict (only when the case pins it).
    grounded_ok = True
    expected_grounded = case.get("should_be_grounded")
    if expected_grounded is not None:
        actual = answer_question(query, use_llm=False)["grounded"]
        grounded_ok = actual == expected_grounded
        detail["expected_grounded"] = expected_grounded
        detail["actual_grounded"] = actual

    return (keywords_ok and grounded_ok), reply, detail


def main() -> int:
    _quiet_console()
    cases = _load_cases()
    _ensure_index()

    print("VALIDATION REPORT")
    print(_RULE)

    passed = 0
    failures: list[tuple[dict, str, dict]] = []

    for case in cases:
        ok, reply, detail = _score_case(case)
        mark = "✅ PASS" if ok else "❌ FAIL"
        query_preview = case["query"] if len(case["query"]) <= 48 else case["query"][:45] + "..."
        print(f"{case['id']:<11} {mark}  {query_preview}")
        if ok:
            passed += 1
        else:
            failures.append((case, reply, detail))
            if detail.get("missing_keywords"):
                print(f"            expected keywords: {case.get('expected_keywords')}")
                print(f"            missing: {detail['missing_keywords']}")
            if "actual_grounded" in detail and detail["actual_grounded"] != detail["expected_grounded"]:
                print(
                    f"            grounded: expected {detail['expected_grounded']}, "
                    f"got {detail['actual_grounded']}"
                )
            preview = reply.replace("\n", " ")
            print(f'            reply: "{preview[:120]}"')

    total = len(cases)
    failed = total - passed
    pct = (passed / total * 100) if total else 0.0

    print(_RULE)
    print(f"SCORE: {passed}/{total} ({pct:.1f}%)")
    print(f"PASSED: {passed}  FAILED: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())