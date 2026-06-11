"""Tests for the indexer + retriever (PROBLEM_STATEMENT.md sections 4.1, 4.3, 4.4).

These build a real ChromaDB store from the actual ``agents/`` catalog (into a
temporary directory so the project's ``.chroma`` is never touched) and then
query it through ``retriever.search_agents`` / ``search_sections``. A green run
confirms the store is built with both record types, scored, and filterable.
"""

from __future__ import annotations

import pytest

from src import config, index
from src.retriever import search_agents, search_sections


@pytest.fixture(scope="module")
def built_store(tmp_path_factory):
    """Index the real catalog into a temp Chroma path and point config at it."""
    chroma_path = tmp_path_factory.mktemp("chroma")
    # Retriever reads config.CHROMA_PATH at call time, so redirect it here.
    original = config.CHROMA_PATH
    config.CHROMA_PATH = chroma_path
    stats = index.build_index(chroma_path=chroma_path)
    yield stats
    config.CHROMA_PATH = original


def test_index_builds_both_record_types(built_store):
    # One summary record per agent, and multiple section records per agent. The
    # catalog is expected to grow, so assert the relationship, not a fixed count.
    assert built_store["agents"] >= 4
    assert built_store["summary_records"] == built_store["agents"]
    assert built_store["section_records"] > built_store["summary_records"]


def test_recommendation_query_returns_expected_agent(built_store):
    # Acceptance criterion: a UI-automation need -> test-script-generator.
    hits = search_agents("I need to automate UI tests from a live URL", k=3)
    assert hits, "expected at least one agent hit"
    assert hits[0].agent_id == "test-script-generator"
    # Scores are cosine similarity in [0, 1], ordered best-first.
    assert 0.0 <= hits[0].score <= 1.0
    assert hits[0].score >= (hits[-1].score if len(hits) > 1 else 0.0)


def test_metadata_filter_scopes_results(built_store):
    # "fully autonomous" implies autonomy_default == L4 -> only the L4 agent.
    hits = search_agents("fully autonomous agents", k=5, where={"autonomy_default": "L4"})
    assert hits, "filter should still return the matching agent"
    assert {h.agent_id for h in hits} == {"test-script-generator"}
    assert all(h.metadata.get("autonomy_default") == "L4" for h in hits)


def test_section_search_is_scoped_to_agent_and_returns_section(built_store):
    hits = search_sections(
        "What are the inputs?", k=10, where={"agent_id": "test-data-provisioning"}
    )
    assert hits, "expected scoped section hits"
    assert all(h.agent_id == "test-data-provisioning" for h in hits)
    # Every section hit carries its section header.
    assert all(h.section for h in hits)
    # The Inputs section is retrieved among the scoped hits. (Exact rank order is
    # content- and embedding-sensitive; the info path targets a section via a
    # metadata filter rather than relying on raw rank, so membership is the
    # property that matters here — see test_section_filter_targets_a_single_section.)
    assert "Inputs" in {h.section for h in hits}


def test_section_filter_targets_a_single_section(built_store):
    where = {"$and": [{"agent_id": "user-story-analyser"}, {"section": "Outputs"}]}
    hits = search_sections("outputs", k=5, where=where)
    assert hits
    assert all(h.section == "Outputs" and h.agent_id == "user-story-analyser" for h in hits)


def test_list_frontmatter_flattened_into_scalar_metadata(built_store):
    hits = search_agents("test data provisioning", k=8)
    meta = next(h.metadata for h in hits if h.agent_id == "test-data-provisioning")
    # Lists (tags, autonomy_supported, triggers) flattened to comma strings.
    assert isinstance(meta["tags"], str)
    assert "synthetic-data" in meta["tags"]
    assert meta["autonomy_supported"] == "L1, L2, L3"
    # Populated triggers -> comma-joined string plus the "specified" flag (section 8).
    assert meta["triggers"] == "manual, api"
    assert meta["triggers_specified"] is True


def test_reindex_rebuilds_cleanly_without_duplicates(built_store):
    # Re-running the indexer must not accumulate duplicate records.
    stats = index.build_index(chroma_path=config.CHROMA_PATH)
    assert stats["summary_records"] == built_store["summary_records"]
    assert stats["section_records"] == built_store["section_records"]

    client = index.get_client(config.CHROMA_PATH)
    assert index.get_summary_collection(client).count() == stats["summary_records"]
    assert index.get_section_collection(client).count() == stats["section_records"]
