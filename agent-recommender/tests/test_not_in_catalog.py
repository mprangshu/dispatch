"""Tests for the recommendation path's "not in catalog" grounding gate.

When a user asks for a specific named agent that isn't in the catalog, the
recommender should say so honestly — "it may be in development or not yet
added" — instead of recommending a loosely-similar agent or emitting a generic
no-match. This mirrors the info path's TBD grounding gate.

The check runs *before* retrieval, so these tests need no Chroma store; they
inject a stub ``search_fn`` to prove that, when a real catalog agent is named or
no agent is named at all, the normal recommendation path still runs. The
membership check (`router.agent_exists`) reads the live ``agents/`` catalog, so
the "in catalog" case uses an agent that actually exists today
("Data Coverage Agent"). ``use_llm=False`` throughout — no network.
"""

from __future__ import annotations

import pytest

import src.recommender as rec
from src import router
from src.chatbot import handle
from src.info import answer_question
from src.recommender import recommend
from src.retriever import Hit


def _hit(agent_id: str, score: float, name: str) -> Hit:
    """A summary-shaped Hit so the normal path can run without a store."""
    return Hit(
        agent_id=agent_id,
        name=name,
        text=f"{name}\n\n{name} does useful testing work.\n\nTags: testing",
        score=score,
        section=None,
        metadata={"agent_id": agent_id, "name": name, "tags": "testing",
                  "autonomy_default": "L2"},
    )


def _sec_hit(agent_id: str, name: str, section: str, body: str) -> Hit:
    """A section-chunk Hit shaped like the indexer's stored records."""
    return Hit(
        agent_id=agent_id,
        name=name,
        text=f"{name} — {section}\n\n{body}",
        score=0.7,
        section=section,
        metadata={"agent_id": agent_id, "name": name, "section": section},
    )


def _strong_match(query, k=3, where=None):
    """A confident single hit — stands in for a successful retrieval."""
    return [_hit("data-coverage", 0.72, "Data Coverage Agent")]


# ---------------------------------------------------------------------------
# Named agent NOT in the catalog -> the gate fires (no retrieval)
# ---------------------------------------------------------------------------


def test_unknown_named_agent_is_reported_not_in_catalog():
    res = recommend("Is there a Performance Testing Agent?", use_llm=False)
    assert res["not_in_catalog"] is True
    assert res["agents"] == []
    assert res["ambiguous"] is False
    low = res["explanation"].lower()
    assert "in development" in low or "not yet added" in low


def test_not_in_catalog_reply_lists_available_agents():
    res = recommend("Is there a Performance Testing Agent?", use_llm=False)
    # Every real catalog agent is offered as an alternative in the message.
    names = [a.name for a in router.load_agents(router.config.AGENTS_DIR)]
    assert names  # sanity: catalog is readable
    for name in names:
        assert name in res["explanation"]


# ---------------------------------------------------------------------------
# Named agent that IS in the catalog -> normal recommendation path
# ---------------------------------------------------------------------------


def test_named_agent_in_catalog_takes_normal_path():
    # "Data Coverage Agent" exists today, so the gate must NOT fire.
    assert router.agent_exists("Data Coverage Agent") is True
    res = recommend(
        "I need the Data Coverage Agent", use_llm=False, search_fn=_strong_match
    )
    assert res.get("not_in_catalog") is not True
    assert [h.agent_id for h in res["agents"]] == ["data-coverage"]


# ---------------------------------------------------------------------------
# No specific agent named -> normal recommendation path (no false positive)
# ---------------------------------------------------------------------------


def test_generic_need_is_not_a_false_positive():
    res = recommend(
        "I need to automate UI tests", use_llm=False, search_fn=_strong_match
    )
    assert res.get("not_in_catalog") is not True
    assert res["agents"]  # the normal path produced a recommendation


# ---------------------------------------------------------------------------
# End to end through chatbot.handle
# ---------------------------------------------------------------------------


def test_handle_reports_not_in_catalog():
    reply = handle("Is there a Performance Testing Agent?", use_llm=False).lower()
    assert "not" in reply
    assert "catalog" in reply or "development" in reply


# ---------------------------------------------------------------------------
# BUG 1 — noun-only (no "Agent") capability phrases that aren't in the catalog
# ---------------------------------------------------------------------------


def test_capability_phrase_without_agent_word_fires():
    # "Performance testing" has no word "Agent" but names a non-catalog capability.
    res = recommend("I want to do Performance testing", use_llm=False)
    assert res["not_in_catalog"] is True
    assert res["agents"] == []


def test_load_testing_capability_fires():
    res = recommend("I need Load testing capabilities", use_llm=False)
    assert res["not_in_catalog"] is True


def test_generic_ui_phrase_does_not_fire():
    # "UI tests" is too generic / too short a first token to be a named capability.
    res = recommend(
        "I need to automate UI tests", use_llm=False, search_fn=_strong_match
    )
    assert res.get("not_in_catalog") is not True
    assert res["agents"]  # normal recommendation still produced


# ---------------------------------------------------------------------------
# BUG 2 — not-in-catalog takes precedence over the info path; closest appended
# ---------------------------------------------------------------------------


def test_visual_regression_does_not_leak_wrong_agent_tbd(monkeypatch):
    # "Regression" would fuzzily pull in "Regression Healing"; the not-in-catalog
    # result must win and the wrong agent's TBD answer must NOT surface.
    monkeypatch.setattr(
        rec, "search_agents",
        lambda *a, **k: [_hit("regression-healing-deepagent", 0.5,
                              "Regression Healing (DeepAgent)")],
    )
    reply = handle(
        "Do you have a Visual Regression Agent? If not, what's the closest thing?",
        use_llm=False,
    )
    low = reply.lower()
    assert "not in catalog" in low or "development" in low
    assert "tbd" not in low
    assert "not specified" not in low
    # The closest available alternative is surfaced (it exists above threshold).
    assert "closest agent we have is" in low


def test_closest_match_appended_when_asked():
    res = recommend(
        "Do you have a Visual Regression Agent? Anything similar?",
        use_llm=False,
        search_fn=lambda *a, **k: [_hit("regression-healing-deepagent", 0.5,
                                       "Regression Healing (DeepAgent)")],
    )
    assert res["not_in_catalog"] is True
    assert "closest agent we have is" in res["explanation"].lower()
    assert "Regression Healing" in res["explanation"]


def test_closest_not_appended_below_threshold():
    res = recommend(
        "Do you have a Visual Regression Agent? Anything similar?",
        use_llm=False,
        search_fn=lambda *a, **k: [_hit("x", 0.05, "Weak Match")],  # below floor
    )
    assert res["not_in_catalog"] is True
    assert "closest agent" not in res["explanation"].lower()


# ---------------------------------------------------------------------------
# BUG 3 — info questions about non-existent agents don't answer the wrong agent
# ---------------------------------------------------------------------------


def test_info_question_for_nonexistent_agent_is_honest():
    reply = handle(
        "What are the inputs to the Performance Testing Agent?", use_llm=False
    ).lower()
    assert "not in catalog" in reply or "development" in reply
    # The wrong agent ("Test Case Creation — Microsoft Agent Framework") must not leak.
    assert "microsoft" not in reply


def test_info_path_short_message_has_no_agent_list():
    # The info-path not-in-catalog answer must NOT enumerate agents (that could
    # surface the very name fragment the user typed).
    res = answer_question(
        "What are the inputs to the Performance Testing Agent?",
        use_llm=False,
        search_fn=lambda *a, **k: pytest.fail("retriever must not be called"),
    )
    assert res["grounded"] is False
    assert "development" in res["answer"].lower()
    assert "microsoft" not in res["answer"].lower()


def test_real_agent_info_question_still_grounded():
    # A genuine agent must still produce a grounded, retrieved answer.
    body = "| Input | User Story ID | Identifies the story whose data is needed |"
    res = answer_question(
        "What are the inputs to Test Data Provisioning?",
        use_llm=False,
        search_fn=lambda *a, **k: [
            _sec_hit("test-data-provisioning", "Test Data Provisioning", "Inputs", body)
        ],
    )
    assert res["grounded"] is True
    assert "User Story ID" in res["answer"]


# ---------------------------------------------------------------------------
# BUG A — info questions about non-existent agents don't answer the wrong agent
# ---------------------------------------------------------------------------


def test_info_cicd_agent_is_honest_not_wrong_agent():
    reply = handle("What does the CI/CD Agent do?", use_llm=False)
    low = reply.lower()
    assert "not in catalog" in low or "development" in low
    # No wrong-agent content leaks through.
    assert "tbd" not in low
    assert "microsoft" not in low
    assert "test case generation" not in low


# ---------------------------------------------------------------------------
# BUG B — "anything called the X Agent" phrasing is caught by the gate
# ---------------------------------------------------------------------------


def test_anything_called_nonexistent_agent_fires():
    reply = handle(
        "Do you have anything called the Bug Triaging Agent?", use_llm=False
    ).lower()
    assert "not in catalog" in reply or "development" in reply


def test_anything_called_real_agent_does_not_fire():
    # "Test Data Provisioning" is real -> the gate must NOT fire.
    assert rec._looks_like_specific_agent_request(
        "Do you have anything called the Test Data Provisioning?"
    ) is None


# ---------------------------------------------------------------------------
# BUG C — "I need the security scan agent" (no security-scan-agent.md exists)
# ---------------------------------------------------------------------------


def test_security_scan_agent_handled():
    # security-scan-agent.md does not exist -> gate fires (sub-case C1). Either
    # way, the reply must not be a random unrelated shortlist.
    res = recommend("I need the security scan agent", use_llm=False)
    if res.get("not_in_catalog"):
        assert res["agents"] == []
    else:  # sub-case C2: a real agent was found -> a single sensible match
        assert res["agents"]


# ---------------------------------------------------------------------------
# BUG D — name extraction stops at predicate words ("Agent output")
# ---------------------------------------------------------------------------


def test_cicd_agent_output_extracts_clean_name():
    # The extractor must capture "CI/CD", not "CI/CD Agent output".
    name = rec._looks_like_specific_agent_request("What does the CI/CD Agent output?")
    assert name is not None
    assert "output" not in name.lower()
    assert name.lower().startswith("ci/cd")


def test_cicd_agent_output_reply_is_not_in_catalog():
    reply = handle("What does the CI/CD Agent output?", use_llm=False).lower()
    assert "not in catalog" in reply or "development" in reply
    assert "agent output" not in reply


def test_real_agent_output_question_does_not_fire():
    # "Test Script Generator" is real -> the gate must NOT fire (normal path).
    assert rec._looks_like_specific_agent_request(
        "What does the Test Script Generator output?"
    ) is None