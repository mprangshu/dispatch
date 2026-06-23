"""Regression guard — the fixed validation set must score 100%.

Runs every case in ``tests/validation_set.json`` through the chatbot
(``use_llm=False``, offline) and asserts a perfect pass rate. Unlike the
per-module unit tests, this is a *quality* gate over the whole stack: if a
catalog edit, a threshold change, or an embedding-model swap silently degrades
an answer, this test goes red.

The real catalog is indexed into a temp Chroma store (the repo's ``.chroma/`` is
never touched), mirroring the other end-to-end tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import config, index
from src.chatbot import handle
from src.info import answer_question

VALIDATION_SET = Path(__file__).resolve().parent / "validation_set.json"


def _load_cases() -> list[dict]:
    return json.loads(VALIDATION_SET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built_store(tmp_path_factory):
    """Index the real catalog into a temp Chroma path and point config at it."""
    chroma_path = tmp_path_factory.mktemp("chroma_validation")
    original = config.CHROMA_PATH
    config.CHROMA_PATH = chroma_path
    index.build_index(chroma_path=chroma_path)
    yield
    config.CHROMA_PATH = original


def _check(case: dict) -> list[str]:
    """Return a list of failure reasons for ``case`` (empty == pass)."""
    reasons: list[str] = []
    reply = handle(case["query"], use_llm=False)
    low = reply.lower()

    for kw in case.get("expected_keywords", []):
        if kw.lower() not in low:
            reasons.append(f"missing keyword {kw!r}; reply={reply[:120]!r}")

    expected_grounded = case.get("should_be_grounded")
    if expected_grounded is not None:
        actual = answer_question(case["query"], use_llm=False)["grounded"]
        if actual != expected_grounded:
            reasons.append(f"grounded expected {expected_grounded}, got {actual}")

    return reasons


def test_validation_set_is_present_and_well_formed():
    cases = _load_cases()
    assert cases, "validation set must not be empty"
    for case in cases:
        assert {"id", "type", "query", "expected_keywords"} <= set(case)
        assert case["type"] in {"recommend", "info", "clarify"}


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_validation_case_passes(case, built_store):
    reasons = _check(case)
    assert not reasons, f"[{case['id']}] " + " | ".join(reasons)


def test_validation_set_scores_100_percent(built_store):
    cases = _load_cases()
    failures = {c["id"]: _check(c) for c in cases if _check(c)}
    assert not failures, f"validation regressions: {failures}"
