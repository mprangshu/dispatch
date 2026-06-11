"""Tests for the catalog loader and Agent model (PROBLEM_STATEMENT.md 6.1).

These run against the REAL catalog files in ``agents/`` so they double as a
sanity check that the source files match the normalized template (section 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.loader import load_agent, load_agents

AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"


@pytest.fixture(scope="module")
def agents_by_id():
    agents = load_agents(AGENTS_DIR)
    return {a.agent_id: a for a in agents}


def test_all_agents_load():
    agents = load_agents(AGENTS_DIR)
    # The catalog has grown beyond the original four; assert the known agents are
    # all present rather than hard-coding an exact count (it's expected to grow).
    ids = {a.agent_id for a in agents}
    assert {
        "smarttdm-agenticdc",
        "user-story-analyser",
        "test-data-provisioning",
        "test-script-generator",
        "api-contract-validator",
        "mobile-app-tester",
        "security-scan-agent",
        "accessibility-auditor",
    } <= ids
    assert len(agents) == len(ids)  # no duplicate ids


def test_frontmatter_lists_and_scalars_parsed(agents_by_id):
    tdp = agents_by_id["test-data-provisioning"]
    assert tdp.autonomy_default == "L2"
    assert tdp.autonomy_supported == ["L1", "L2", "L3"]
    assert tdp.domain == "testing"
    # Lists stay lists — flattening is the indexer's job, not the loader's.
    assert isinstance(tdp.tags, list)
    assert "synthetic-data" in tdp.tags


def test_empty_triggers_is_empty_list_not_error(tmp_path):
    # Absence of triggers must parse as "not specified" (empty list), not a
    # failure (PROBLEM_STATEMENT.md section 8). Tested against a synthetic file so
    # it stays valid regardless of whether any catalog agent currently omits them.
    p = tmp_path / "no-triggers.md"
    p.write_text(
        "---\n"
        "agent_id: no-triggers\n"
        "name: No Triggers Agent\n"
        "domain: testing\n"
        "triggers: []\n"
        "---\n\n"
        "## Overview\nAn agent whose triggers are not specified.\n",
        encoding="utf-8",
    )
    agent = load_agent(p)
    assert agent.triggers == []


def test_populated_triggers_parsed(agents_by_id):
    usa = agents_by_id["user-story-analyser"]
    assert usa.triggers == ["manual", "api", "webhook"]


def test_get_section_returns_text(agents_by_id):
    usa = agents_by_id["user-story-analyser"]
    inputs = usa.get_section("Inputs")
    assert inputs is not None
    assert inputs.strip() != ""
    # Tables are preserved as raw markdown, not parsed.
    assert "|" in inputs


def test_get_section_is_case_insensitive(agents_by_id):
    usa = agents_by_id["user-story-analyser"]
    assert usa.get_section("inputs") == usa.get_section("Inputs")


def test_missing_section_returns_none(agents_by_id):
    usa = agents_by_id["user-story-analyser"]
    assert usa.get_section("Nonexistent Section") is None


def test_summary_text_includes_name_overview_and_tags(agents_by_id):
    tdp = agents_by_id["test-data-provisioning"]
    summary = tdp.summary_text()
    assert tdp.name in summary
    assert "provisions" in summary  # from the Overview section
    assert "synthetic-data" in summary  # from tags


def test_source_path_is_recorded(agents_by_id):
    tdp = agents_by_id["test-data-provisioning"]
    assert tdp.source_path.endswith("test-data-provisioning.md")


def test_load_single_agent_directly():
    agent = load_agent(AGENTS_DIR / "test-script-generator.md")
    assert agent.agent_id == "test-script-generator"
    assert agent.get_section("Overview") is not None
