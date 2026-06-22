"""Comprehensive edge-case suite — boundary behaviour of the whole system.

Each test pins one specific failure mode to an explicit expected behaviour
grounded in PROBLEM_STATEMENT.md (empty/missing catalog, malformed files,
retrieval boundaries, info/recommendation edges, and the HTTP layer).

Patterns (mirroring TESTING.md): everything runs offline — ``use_llm=False``
and/or injected ``search_fn=`` stubs, no live API calls. Tests that need a real
index build into a ``tmp_path`` and restore ``config.AGENTS_DIR`` /
``config.CHROMA_PATH`` afterwards, so the repo's ``.chroma/`` and ``agents/`` are
never touched.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src import config, index
from src.chatbot import handle
from src.info import answer_question, detect_section
from src.loader import load_agent, load_agents
from src.recommender import recommend
from src.retriever import Hit, search_agents, search_sections


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _clear_caches() -> None:
    """Drop every catalog-derived cache so a swapped catalog is seen at once."""
    from src.chatbot import available_agent_names
    from src.recommender import _catalog_vocab
    from src.router import _agent_terms

    _agent_terms.cache_clear()
    available_agent_names.cache_clear()
    _catalog_vocab.cache_clear()


@contextmanager
def build_catalog(tmp_path, files: dict[str, str]):
    """Point the catalog + store at a temp dir built from ``files`` and index it.

    ``files`` maps filename -> file content; ``{}`` builds an empty catalog.
    Restores ``config.AGENTS_DIR`` / ``config.CHROMA_PATH`` on exit.
    """
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    for fname, content in files.items():
        (agents_dir / fname).write_text(content, encoding="utf-8")
    chroma = tmp_path / "chroma"

    orig_agents, orig_chroma = config.AGENTS_DIR, config.CHROMA_PATH
    config.AGENTS_DIR = agents_dir
    config.CHROMA_PATH = chroma
    _clear_caches()
    stats = index.build_index(agents_dir=agents_dir, chroma_path=chroma)
    try:
        yield stats
    finally:
        config.AGENTS_DIR, config.CHROMA_PATH = orig_agents, orig_chroma
        _clear_caches()


@pytest.fixture(scope="module")
def real_store(tmp_path_factory):
    """Index the real catalog into a temp Chroma path (AGENTS_DIR unchanged)."""
    chroma = tmp_path_factory.mktemp("chroma_edge")
    orig = config.CHROMA_PATH
    config.CHROMA_PATH = chroma
    index.build_index(chroma_path=chroma)
    yield
    config.CHROMA_PATH = orig


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from api import app

    return TestClient(app)


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


_ONE_AGENT_MD = (
    "---\n"
    "agent_id: solo\n"
    "name: Solo Agent\n"
    "domain: testing\n"
    "tags: [automation, ui, web, testing]\n"
    "autonomy_default: L2\n"
    "autonomy_supported: [L2]\n"
    "triggers: [manual]\n"
    "---\n\n"
    "## Overview\n"
    "Automates UI tests against a live web URL end to end, generating and "
    "running browser scripts.\n"
)


# ===========================================================================
# GROUP A — Empty / missing catalog
# ===========================================================================


def test_a1_load_agents_on_empty_dir_returns_empty(tmp_path):
    empty = tmp_path / "agents"
    empty.mkdir()
    assert load_agents(empty) == []


def test_a2_build_index_on_empty_catalog_is_clean(tmp_path):
    with build_catalog(tmp_path, {}) as stats:
        assert stats["agents"] == 0
        assert stats["summary_records"] == 0
        assert stats["section_records"] == 0


def test_a3_handle_with_empty_catalog_says_no_agents(tmp_path):
    with build_catalog(tmp_path, {}):
        reply = handle("I need an agent", use_llm=False)
        low = reply.lower()
        assert reply  # not a crash / not blank
        assert "no agents are currently available" in low


def test_a4_get_agents_with_empty_catalog_returns_empty(tmp_path, api_client):
    empty = tmp_path / "agents"
    empty.mkdir()
    orig = config.AGENTS_DIR
    config.AGENTS_DIR = empty
    _clear_caches()
    try:
        resp = api_client.get("/agents")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        config.AGENTS_DIR = orig
        _clear_caches()


# ===========================================================================
# GROUP B — Malformed / partial agent files
# ===========================================================================


def test_b1_no_frontmatter_loads_with_stem_id(tmp_path):
    p = tmp_path / "lonely.md"
    p.write_text("## Overview\nDoes a useful thing.\n", encoding="utf-8")
    agent = load_agent(p)
    assert agent.agent_id == "lonely"  # fallback to filename stem
    assert agent.get_section("Overview") == "Does a useful thing."


def test_b2_no_body_sections_loads_with_empty_sections(tmp_path):
    p = tmp_path / "bare.md"
    p.write_text("---\nagent_id: bare\nname: Bare\n---\n", encoding="utf-8")
    agent = load_agent(p)
    assert agent.sections == {}
    assert agent.agent_id == "bare"


def test_b3_missing_section_returns_none(tmp_path):
    p = tmp_path / "partial.md"
    p.write_text(
        "---\nagent_id: partial\nname: Partial\n---\n\n## Overview\nHi there.\n",
        encoding="utf-8",
    )
    agent = load_agent(p)
    assert agent.get_section("Deployment") is None  # absent, not an error
    assert agent.get_section("Overview") == "Hi there."


def test_b4_malformed_yaml_falls_back_to_defaults(tmp_path):
    # Unterminated string in the frontmatter must not crash the loader.
    p = tmp_path / "broken.md"
    p.write_text(
        '---\nname: "unterminated\nagent_id: broken\n---\n\n## Overview\nOkay.\n',
        encoding="utf-8",
    )
    agent = load_agent(p)  # must not raise
    assert agent.agent_id == "broken"  # frontmatter dropped -> stem fallback
    assert agent.get_section("Overview") == "Okay."


# ===========================================================================
# GROUP C — Retrieval edge cases
# ===========================================================================


def test_c1_search_agents_on_empty_collection(tmp_path):
    with build_catalog(tmp_path, {}):
        assert search_agents("anything at all", k=3) == []


def test_c2_search_sections_no_match_returns_empty(real_store):
    hits = search_sections("inputs", k=5, where={"agent_id": "does-not-exist"})
    assert hits == []


def test_c2_info_path_widens_when_section_filter_empty():
    inputs_hit = _sec_hit(
        "test-data-provisioning", "Test Data Provisioning", "Inputs",
        "| User Story ID | Yes | Identifies the story whose data is needed |",
    )
    calls: list = []

    def stub(query, k=5, where=None):
        calls.append(where)
        if where and "$and" in where:  # tight agent+section filter -> nothing
            return []
        return [inputs_hit]

    res = answer_question(
        "What are the inputs to Test Data Provisioning?",
        use_llm=False,
        search_fn=stub,
    )
    assert res["grounded"] is True
    assert len(calls) >= 2  # it widened past the empty tight filter


def test_c3_very_long_query_returns_a_reply(real_store):
    query = "automate browser tests on a website " * 20  # > 512 chars
    assert len(query) > 512
    reply = handle(query, use_llm=False)
    assert isinstance(reply, str) and reply


def test_c4_special_characters_only_clarifies():
    reply = handle("???!!!@@@", use_llm=False)
    low = reply.lower()
    assert "not sure" in low or "describe a task" in low


def test_c5_k_larger_than_catalog_returns_what_exists(real_store):
    hits = search_agents("testing automation", k=100)
    assert isinstance(hits, list)
    assert 0 < len(hits) <= 100  # however many agents exist, no error


# ===========================================================================
# GROUP D — Info path edge cases
# ===========================================================================


@pytest.mark.parametrize(
    "query",
    [
        "What are the inputs to Test Data Provisioning?",
        "What does Test Data Provisioning output?",
        "What hardware does Test Data Provisioning need?",
        "Tell me about Test Data Provisioning",
    ],
)
def test_d1_all_sections_tbd_is_never_grounded(query):
    tbd = _sec_hit(
        "test-data-provisioning", "Test Data Provisioning", "Inputs",
        "**Hardware:** TBD\n**Software:** TBD",
    )
    res = answer_question(query, use_llm=False, search_fn=lambda *a, **k: [tbd])
    assert res["grounded"] is False


def test_d2_two_agent_names_picks_one_and_answers(real_store):
    reply = handle(
        "compare Test Data Provisioning and Test Script Generator", use_llm=False
    )
    assert isinstance(reply, str) and reply  # no crash
    assert "Test Data Provisioning" in reply or "Test Script Generator" in reply


def test_d3_no_section_detected_still_answers():
    assert detect_section("asdf qwer zxcv") is None  # no attribute word
    hit = _sec_hit(
        "test-data-provisioning", "Test Data Provisioning", "Overview",
        "Provisions ready-to-use test data for the linked test cases.",
    )
    res = answer_question("asdf qwer zxcv", use_llm=False, search_fn=lambda *a, **k: [hit])
    assert res["grounded"] is True
    assert "Provisions ready-to-use" in res["answer"]


# ===========================================================================
# GROUP E — Recommendation edge cases
# ===========================================================================


def test_e1_filter_matches_nothing_is_no_match():
    # The L1 filter is applied but matches no agent (stub returns nothing).
    res = recommend("I need an L1 agent", use_llm=False, search_fn=lambda q, k=3, where=None: [])
    assert res["agents"] == []
    assert res["ambiguous"] is False
    assert "match" in res["explanation"].lower()


def test_e2_single_agent_catalog_recommends_it(tmp_path):
    with build_catalog(tmp_path, {"solo.md": _ONE_AGENT_MD}):
        res = recommend("automate UI tests on a website", use_llm=False)
        assert res["ambiguous"] is False
        assert [h.agent_id for h in res["agents"]] == ["solo"]


def test_e3_unrelated_long_sentence_triggers_no_match(real_store):
    query = (
        "the weather today is sunny and the cat sat on the mat while the children "
        "played in the park eating ice cream near the river under the tall green "
        "trees as colourful birds sang softly in the warm afternoon breeze"
    )
    res = recommend(query, use_llm=False)
    assert res["agents"] == []
    assert res["ambiguous"] is False


# ===========================================================================
# GROUP F — API / interface edge cases
# ===========================================================================


def test_f1_chat_empty_message_returns_clarify(api_client):
    resp = api_client.post("/chat", json={"message": "", "use_llm": False})
    assert resp.status_code == 200  # not a 422
    assert resp.json()["reply"]


def test_f2_chat_long_message_returns_reply(api_client, real_store):
    resp = api_client.post(
        "/chat", json={"message": "automate browser tests " * 100, "use_llm": False}
    )
    assert resp.status_code == 200
    assert resp.json()["reply"]


def test_f3_chat_use_llm_omitted_defaults_true(api_client):
    # "hi" classifies as clarify (no retrieval needed), so this needs no store.
    resp = api_client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200  # not a 422
    assert resp.json()["reply"]


def test_f4_health_reports_llm_availability(api_client):
    from src import llm

    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["llm_available"] == llm.available()
