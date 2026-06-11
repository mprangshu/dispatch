"""Shared Chroma store singletons — one client, one embedding fn, cached collections.

Both ``index.py`` (write side) and ``retriever.py`` (read side) need the same
persistent Chroma client, the same embedding function, and handles to the two
collections. Previously each query re-opened the client and re-instantiated the
onnx embedding wrapper, which was slow and triggered Chroma "multiple client"
warnings. This module owns those as **process-level singletons** so they're
created once and reused.

Plain module globals are used (not ``lru_cache``) so they survive across calls
and can be explicitly reset by :func:`refresh_catalog_caches` after a re-index.
The client is re-opened only when a different path is requested (e.g. tests
pointing ``config.CHROMA_PATH`` at a temp dir).
"""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from . import config

# Process-level singletons. Reset selectively by refresh_catalog_caches().
_client = None
_client_path: Path | None = None
_embedding_function = None
_summary_collection = None
_section_collection = None


def get_embedding_function():
    """Return the cached embedding function, building it once per process.

    Defaults to ChromaDB's built-in model (all-MiniLM-L6-v2, runs locally via
    onnxruntime — no API key needed). Built once and reused so queries don't
    re-create the onnx wrapper on every call. Swap the function here to change
    the embedding model for both indexing and retrieval (PROBLEM_STATEMENT.md
    section 2).
    """
    global _embedding_function
    if _embedding_function is None:
        _embedding_function = embedding_functions.DefaultEmbeddingFunction()
    return _embedding_function


def get_client(path: str | Path | None = None) -> chromadb.api.ClientAPI:
    """Return the cached persistent Chroma client, opening it only once.

    Re-opens only if a different ``path`` is requested than the one currently
    cached; on a re-open the cached collection handles are dropped (they belong
    to the old client).
    """
    global _client, _client_path, _summary_collection, _section_collection
    target = Path(path) if path is not None else Path(config.CHROMA_PATH)
    if _client is None or _client_path != target:
        target.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(target))
        _client_path = target
        # Collections from a previous client are stale.
        _summary_collection = None
        _section_collection = None
    return _client


def get_summary_collection(client=None):
    """Cached handle to the agent-summary collection (coarse, recommendation).

    ``client`` is accepted for API compatibility with the previous index.py
    signature; when omitted the cached client is used.
    """
    global _summary_collection
    active = get_client() if client is None else client
    if _summary_collection is None:
        _summary_collection = active.get_collection(
            name=config.SUMMARY_COLLECTION,
            embedding_function=get_embedding_function(),
        )
    return _summary_collection


def get_section_collection(client=None):
    """Cached handle to the section-chunk collection (fine, info-lookup)."""
    global _section_collection
    active = get_client() if client is None else client
    if _section_collection is None:
        _section_collection = active.get_collection(
            name=config.SECTION_COLLECTION,
            embedding_function=get_embedding_function(),
        )
    return _section_collection


def refresh_catalog_caches() -> None:
    """Invalidate every catalog-derived cache after a re-index.

    Called at the end of ``index.build_index`` so a long-running process (e.g.
    the FastAPI server) immediately reflects an added/removed/edited agent
    without a restart. Specifically it:

    1. drops the cached Chroma collection handles here (the next query re-opens
       them against the freshly rebuilt collections), and
    2. clears the ``lru_cache`` on ``router._agent_terms`` and
       ``chatbot.available_agent_names`` so agent-name recognition and the
       edge-case listings rebuild from the current catalog.

    The cached client and embedding function are intentionally kept — only
    catalog-derived state is dropped.
    """
    global _summary_collection, _section_collection
    _summary_collection = None
    _section_collection = None
    # Lazy imports: router/chatbot pull in retriever -> store at module load, so
    # importing them at module top would be circular. By call time (a build has
    # run) they're fully initialized.
    from .chatbot import available_agent_names
    from .router import _agent_terms

    _agent_terms.cache_clear()
    available_agent_names.cache_clear()
