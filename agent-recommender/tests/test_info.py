"""Tests for the RAG info path (PROBLEM_STATEMENT.md section 4.4).

Covers the three cases the Phase 4 brief calls for:

* an **inputs/outputs** question -> a grounded answer drawn from the retrieved
  section (and scoped to the right agent + section);
* a **missing-data** question (Deployment is ``TBD``) -> ``grounded=False`` and
  an honest "I don't have that", never a fabricated spec;
* plus section detection, the widen-on-empty retrieval fallback, and the
  no-results case.

The retriever is **stubbed** against the section-7 ``Hit`` contract so the
grounding/scoping logic is exercised deterministically with no embeddings or
network. ``use_llm=False`` throughout, so answers come from the deterministic
fallback and the grounding gate, not a live model. ``find_agent`` /
``detect_section`` run for real (local catalog read only).
"""

from __future__ import annotations

import pytest

from src.info import answer_question, detect_section
from src.retriever import Hit


def _sec_hit(agent_id: str, name: str, section: str, body: str, score: float = 0.7) -> Hit:
    """A section-chunk Hit shaped like the indexer's records (prefixed text)."""
    return Hit(
        agent_id=agent_id,
        name=name,
        text=f"{name} — {section}\n\n{body}",
        score=score,
        section=section,
        metadata={"agent_id": agent_id, "name": name, "section": section},
    )


# ---------------------------------------------------------------------------
# Section detection (pure)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        ("What are the inputs to Test Data Provisioning?", "Inputs"),
        ("What does it output?", "Outputs"),
        ("What's the autonomy level of the User Story Analyser?", "Autonomy Level"),
        ("What hardware does it need?", "Deployment"),
        ("How is it triggered?", "Triggers"),
        ("What are its limitations?", "Limitations"),
        ("I need to automate UI tests", None),
    ],
)
def test_detect_section(query, expected):
    assert detect_section(query) == expected


# ---------------------------------------------------------------------------
# Inputs question -> grounded, scoped to agent + section
# ---------------------------------------------------------------------------


def test_inputs_question_is_grounded_and_scoped():
    body = (
        "| Input | Required | Description |\n"
        "| User Story ID | Yes | Identifies the story whose test cases need data |"
    )
    hit = _sec_hit("test-data-provisioning", "Test Data Provisioning", "Inputs", body)
    captured = {}

    def stub(query, k=5, where=None):
        captured["where"] = where
        return [hit]

    res = answer_question(
        "What are the inputs to Test Data Provisioning?",
        use_llm=False,
        search_fn=stub,
    )

    assert res["grounded"] is True
    assert "User Story ID" in res["answer"]
    assert res["sources"] and res["sources"][0].section == "Inputs"
    # Scoped to the right agent AND section via the metadata filter.
    assert captured["where"] == {
        "$and": [
            {"agent_id": "test-data-provisioning"},
            {"section": "Inputs"},
        ]
    }


def test_outputs_question_is_grounded():
    body = "| Test Report | Pass/fail results per test with screenshots |"
    hit = _sec_hit("test-script-generator", "Test Script Generator Agent", "Outputs", body)

    res = answer_question(
        "What does the Test Script Generator Agent output?",
        use_llm=False,
        search_fn=lambda *a, **k: [hit],
    )

    assert res["grounded"] is True
    assert "Test Report" in res["answer"]


# ---------------------------------------------------------------------------
# Missing data (Deployment is TBD) -> honest, never fabricated
# ---------------------------------------------------------------------------


def test_missing_deployment_is_not_hallucinated():
    hit = _sec_hit(
        "user-story-analyser",
        "User Story Analyser Agent",
        "Deployment",
        "**Hardware:** TBD\n**Software:** TBD",
    )

    res = answer_question(
        "What hardware does the User Story Analyser need?",
        use_llm=False,
        search_fn=lambda *a, **k: [hit],
    )

    assert res["grounded"] is False
    assert "don't have" in res["answer"].lower()
    # No invented hardware specs leaked into the answer.
    for invented in ("gpu", "cpu", "ram", "gb", "cores"):
        assert invented not in res["answer"].lower()


def test_not_specified_section_is_not_grounded():
    hit = _sec_hit(
        "test-data-provisioning", "Test Data Provisioning", "Limitations",
        "Not specified in source.",
    )

    res = answer_question(
        "What are the limitations of Test Data Provisioning?",
        use_llm=False,
        search_fn=lambda *a, **k: [hit],
    )

    assert res["grounded"] is False
    assert "don't have" in res["answer"].lower()


# ---------------------------------------------------------------------------
# Retrieval fallbacks
# ---------------------------------------------------------------------------


def test_widens_when_section_filter_is_empty():
    """A too-tight agent+section filter returns nothing -> widen to agent."""
    inputs_hit = _sec_hit(
        "test-data-provisioning", "Test Data Provisioning", "Inputs",
        "| User Story ID | Yes | ... |",
    )
    calls: list[dict | None] = []

    def stub(query, k=5, where=None):
        calls.append(where)
        # First (agent+section) call yields nothing; agent-only call succeeds.
        if where and "$and" in where:
            return []
        return [inputs_hit]

    res = answer_question(
        "What are the inputs to Test Data Provisioning?",
        use_llm=False,
        search_fn=stub,
    )

    assert res["grounded"] is True
    assert len(calls) >= 2  # it widened
    assert calls[1] == {"agent_id": "test-data-provisioning"}


def test_no_results_is_honest():
    res = answer_question(
        "What hardware does the User Story Analyser need?",
        use_llm=False,
        search_fn=lambda *a, **k: [],
    )

    assert res["grounded"] is False
    assert res["sources"] == []
