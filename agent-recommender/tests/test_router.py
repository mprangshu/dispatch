"""Tests for the intent router (PROBLEM_STATEMENT.md section 4.2).

Covers intent classification on representative messages (recommend / info /
clarify) and the catalog-driven agent-name detection that disambiguates "info"
questions. The LLM is disabled (``use_llm=False``) so classification is purely
rule-based, deterministic, and needs no network.

``find_agent`` reads the real ``agents/`` catalog (a local file read, no
embeddings/network), proving names are recognized from the data, not hard-coded.
"""

from __future__ import annotations

import pytest

from src.router import detect_intent, find_agent


@pytest.mark.parametrize(
    "message,expected",
    [
        # recommend — describes a need / asks for a fitting agent.
        ("I want to turn manual test cases into automated UI scripts", "recommend"),
        ("I need to automate UI tests from a live URL", "recommend"),
        ("which agent should I use to analyse user stories", "recommend"),
        ("recommend an agent for generating synthetic test data", "recommend"),
        ("which agents are fully autonomous", "recommend"),
        # info — asks about a specific named agent's details.
        ("What's the autonomy level of the User Story Analyser?", "info"),
        ("What does Test Data Provisioning output?", "info"),
        ("What are the inputs to the Test Script Generator Agent?", "info"),
        ("What hardware does the User Story Analyser need?", "info"),
        # clarify — too vague to act on.
        ("hi", "clarify"),
        ("help", "clarify"),
        ("I'm not sure", "clarify"),
        ("", "clarify"),
    ],
)
def test_detect_intent(message, expected):
    assert detect_intent(message, use_llm=False) == expected


@pytest.mark.parametrize(
    "message",
    [
        # Definitional questions about a named catalog agent -> info, not clarify.
        "What is the User Story Analyser?",
        "Tell me about Test Data Provisioning",
        "Describe the Test Script Generator",
        "What's SmartTDM AgenticDC?",
    ],
)
def test_definitional_question_about_named_agent_is_info(message):
    assert detect_intent(message, use_llm=False) == "info"


@pytest.mark.parametrize(
    "message,expected_id",
    [
        ("What does Test Data Provisioning output?", "test-data-provisioning"),
        ("autonomy level of the User Story Analyser", "user-story-analyser"),
        ("inputs to the Test Script Generator Agent", "test-script-generator"),
        ("tell me about smarttdm-agenticdc", "smarttdm-agenticdc"),
        # No agent named -> None (a cross-catalog ask, not a lookup).
        ("which agents are fully autonomous", None),
        ("I need to automate UI tests from a live URL", None),
    ],
)
def test_find_agent(message, expected_id):
    assert find_agent(message) == expected_id
