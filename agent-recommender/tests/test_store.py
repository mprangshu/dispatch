"""Tests for the cached Chroma store and post-reindex cache invalidation.

Two improvements are covered:

1. **Client/embedding caching** — the persistent Chroma client is opened once
   and reused across queries, instead of being re-created on every search.
2. **Cache invalidation after re-index** — ``build_index()`` clears the
   catalog-derived caches, so a newly added agent is recognized immediately by
   ``router.find_agent`` without a process restart (the long-running-server
   scenario).

Both run against a throwaway store in a temp dir; ``config.CHROMA_PATH`` and the
``store`` singletons are restored after each test by the fixture.
"""

from __future__ import annotations

import chromadb
import pytest

import src.index as index
import src.router as router
import src.store as store
from src import build_index, config
from src.loader import load_agents
from src.models import Agent
from src.retriever import search_agents
from src.router import find_agent


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    """Point config.CHROMA_PATH at a temp dir and reset the store singletons."""
    monkeypatch.setattr(config, "CHROMA_PATH", tmp_path / "chroma")
    monkeypatch.setattr(store, "_client", None)
    monkeypatch.setattr(store, "_client_path", None)
    monkeypatch.setattr(store, "_summary_collection", None)
    monkeypatch.setattr(store, "_section_collection", None)
    yield


# ---------------------------------------------------------------------------
# Improvement 1 — the client is opened once and reused
# ---------------------------------------------------------------------------


def test_client_opened_once_across_searches(temp_store, monkeypatch):
    build_index()  # builds the store at the temp path (opens a client internally)

    # Count PersistentClient instantiations from here on.
    real_pc = chromadb.PersistentClient
    calls = {"n": 0}

    def counting_pc(*args, **kwargs):
        calls["n"] += 1
        return real_pc(*args, **kwargs)

    monkeypatch.setattr(chromadb, "PersistentClient", counting_pc)
    # Force the next access to (re)open a client, then prove it's reused.
    monkeypatch.setattr(store, "_client", None)
    monkeypatch.setattr(store, "_client_path", None)
    monkeypatch.setattr(store, "_summary_collection", None)
    monkeypatch.setattr(store, "_section_collection", None)

    search_agents("automate UI tests from a live URL", k=2)
    search_agents("provision synthetic test data", k=2)

    # Opened exactly once; the second search reused the cached client.
    assert calls["n"] == 1


def test_embedding_function_is_a_singleton(temp_store):
    # The embedding function is built once and reused (no per-query onnx rebuild).
    assert store.get_embedding_function() is store.get_embedding_function()


# ---------------------------------------------------------------------------
# Improvement 2 — re-index invalidates the catalog caches
# ---------------------------------------------------------------------------


def test_new_agent_recognized_after_reindex(temp_store, monkeypatch):
    build_index()

    # An existing agent is recognized; a brand-new one is not yet known.
    assert find_agent("Test Data Provisioning") == "test-data-provisioning"
    assert find_agent("Quantum Fuzz Tester") is None

    # Simulate adding a new agent to the catalog by having the loader return an
    # extra agent (router builds its name set from here; index writes it).
    augmented = load_agents(config.AGENTS_DIR) + [
        Agent(
            agent_id="quantum-fuzz-tester",
            name="Quantum Fuzz Tester",
            domain="testing",
            tags=["fuzzing", "quantum"],
            autonomy_default="L2",
            autonomy_supported=["L2"],
            triggers=[],
            sections={"Overview": "Fuzzes quantum circuits to surface edge-case failures."},
            source_path="<synthetic>",
        )
    ]
    monkeypatch.setattr(router, "load_agents", lambda *a, **k: augmented)
    monkeypatch.setattr(index, "load_agents", lambda *a, **k: augmented)

    # Re-index; build_index() calls refresh_catalog_caches() at the end, which
    # clears router._agent_terms' lru_cache.
    build_index()

    # Recognized immediately — no process restart needed.
    assert find_agent("Quantum Fuzz Tester") == "quantum-fuzz-tester"


def test_refresh_clears_router_and_chatbot_caches(temp_store, monkeypatch):
    import src.chatbot as chatbot

    build_index()
    # Prime both caches.
    find_agent("Test Data Provisioning")
    chatbot.available_agent_names()
    assert router._agent_terms.cache_info().currsize == 1
    assert chatbot.available_agent_names.cache_info().currsize == 1

    store.refresh_catalog_caches()

    assert router._agent_terms.cache_info().currsize == 0
    assert chatbot.available_agent_names.cache_info().currsize == 0
