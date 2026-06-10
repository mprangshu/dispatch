"""Tests for the recommendation path (PROBLEM_STATEMENT.md sections 4.3, 4.5).

Covers the three cases the Phase 3 brief calls for — a clear single match, an
ambiguous case, and a metadata-filtered query — plus filter detection and the
no-match/out-of-scope edge.

Two styles are used deliberately:

* The clear-match and metadata-filter tests run against a **real** ChromaDB
  store built from the actual ``agents/`` catalog (the acceptance criteria), so
  they prove end-to-end ranking and filtering work.
* The ambiguous and no-match tests **inject a stub** ``search_fn`` returning
  hand-crafted ``Hit`` scores. That keeps the threshold logic deterministic and
  fast (no embeddings) — and exercises the section-7 contract directly.

The LLM is disabled (``use_llm=False``) throughout so explanations come from the
deterministic fallback and tests never make a network call.
"""

from __future__ import annotations

import pytest

from src import config, index
from src.recommender import detect_filter, recommend
from src.retriever import Hit


@pytest.fixture(scope="module")
def built_store(tmp_path_factory):
    """Index the real catalog into a temp Chroma path and point config at it."""
    chroma_path = tmp_path_factory.mktemp("chroma")
    original = config.CHROMA_PATH
    config.CHROMA_PATH = chroma_path
    index.build_index(chroma_path=chroma_path)
    yield
    config.CHROMA_PATH = original


def _hit(agent_id: str, score: float, name: str, autonomy: str = "L2") -> Hit:
    """A summary-shaped Hit for stubbed searches."""
    return Hit(
        agent_id=agent_id,
        name=name,
        text=f"{name}\n\n{name} does useful testing work.\n\nTags: testing",
        score=score,
        section=None,
        metadata={"agent_id": agent_id, "name": name, "tags": "testing",
                  "autonomy_default": autonomy},
    )


# ---------------------------------------------------------------------------
# Implied metadata-filter detection (pure, fast)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        ("which agents are fully autonomous", {"autonomy_default": "L4"}),
        ("I want a fully-automated agent", {"autonomy_default": "L4"}),
        ("show me an L3 agent", {"autonomy_default": "L3"}),
        ("I need to automate UI tests from a live URL", None),
    ],
)
def test_detect_filter(query, expected):
    assert detect_filter(query) == expected


# ---------------------------------------------------------------------------
# Clear single match (real index) — the headline acceptance criterion
# ---------------------------------------------------------------------------


def test_clear_single_match(built_store):
    res = recommend("I need to automate UI tests from a live URL", use_llm=False)
    assert res["ambiguous"] is False
    assert [h.agent_id for h in res["agents"]] == ["test-script-generator"]
    assert "Test Script Generator" in res["explanation"]


# ---------------------------------------------------------------------------
# Metadata-filtered query (real index)
# ---------------------------------------------------------------------------


def test_metadata_filtered_query(built_store):
    # "fully autonomous" -> autonomy_default == L4 -> only the L4 agent.
    res = recommend("which agents are fully autonomous", use_llm=False)
    assert {h.agent_id for h in res["agents"]} == {"test-script-generator"}
    assert all(h.metadata.get("autonomy_default") == "L4" for h in res["agents"])


# ---------------------------------------------------------------------------
# Ambiguous case (stubbed) — comparable scores -> a shortlist
# ---------------------------------------------------------------------------


def test_ambiguous_returns_shortlist():
    def fake_search(query, k=3, where=None):
        # Top two are within AMBIGUITY_DELTA; the third is far below.
        return [
            _hit("a", 0.61, "Agent A"),
            _hit("b", 0.57, "Agent B"),
            _hit("c", 0.30, "Agent C"),
        ]

    res = recommend("help me with testing", use_llm=False, search_fn=fake_search)
    assert res["ambiguous"] is True
    assert [h.agent_id for h in res["agents"]] == ["a", "b"]  # "c" excluded (too far)
    assert "Agent A" in res["explanation"] and "Agent B" in res["explanation"]


def test_clear_match_when_runner_up_is_far_behind():
    def fake_search(query, k=3, where=None):
        return [_hit("a", 0.80, "Agent A"), _hit("b", 0.40, "Agent B")]

    res = recommend("a very specific need", use_llm=False, search_fn=fake_search)
    assert res["ambiguous"] is False
    assert [h.agent_id for h in res["agents"]] == ["a"]


# ---------------------------------------------------------------------------
# No match / out of scope (stubbed)
# ---------------------------------------------------------------------------


def test_no_match_when_scores_too_low():
    def fake_search(query, k=3, where=None):
        return [_hit("a", 0.05, "Agent A")]  # below NO_MATCH_SCORE, no filter

    res = recommend("how do I bake a cake", use_llm=False, search_fn=fake_search)
    assert res["agents"] == []
    assert res["ambiguous"] is False
    assert "couldn't find" in res["explanation"].lower()


def test_no_match_when_filter_matches_nothing():
    def fake_search(query, k=3, where=None):
        assert where == {"autonomy_default": "L1"}  # filter was applied
        return []

    res = recommend("I need an L1 agent", use_llm=False, search_fn=fake_search)
    assert res["agents"] == []
    assert res["ambiguous"] is False