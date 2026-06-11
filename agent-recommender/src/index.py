"""Indexer — build the persistent ChromaDB store from the `agents/` catalog.

Offline and re-runnable. Scans ``AGENTS_DIR``, parses each file via
``loader.py``, and writes two kinds of records (PROBLEM_STATEMENT.md
section 4.1):

* **Agent-summary records** — one per agent (coarse), embedding a concise
  summary (name + overview + tags). Used by the recommendation path.
* **Section-chunk records** — one per body section (fine), each carrying
  ``agent_id``, ``name``, ``section`` and the frontmatter fields as metadata.
  Used by the info-lookup (RAG) path.

Re-running rebuilds the store cleanly: both collections are dropped and
recreated from the current files, so adding/removing/editing an `.md` file and
re-indexing is the only step needed to update the catalog (no code changes —
PROBLEM_STATEMENT.md section 9).

This module also owns the shared Chroma client / embedding function so the
indexer and the retriever agree on how the store is opened (path, collection
names, distance space). The embedding function is swappable in one place here
without touching the rest of the architecture (PROBLEM_STATEMENT.md section 2).
"""

from __future__ import annotations

from pathlib import Path

from . import config
from .loader import load_agents
from .models import Agent
from .store import (
    get_client,
    get_embedding_function,
    get_section_collection,
    get_summary_collection,
    refresh_catalog_caches,
)

# The shared Chroma client, embedding function, and collection accessors now
# live in ``store.py`` as process-level singletons (so they're not re-created on
# every query). They're re-exported here so index.py's public API is unchanged.
# ``refresh_catalog_caches`` is used by build_index() below to invalidate
# catalog-derived caches after a rebuild.

# ---------------------------------------------------------------------------
# Metadata flattening (Chroma metadata values must be str/int/float/bool)
# ---------------------------------------------------------------------------


def _join(values: list[str]) -> str:
    """Flatten a list field into a comma-separated string ("" when empty)."""
    return ", ".join(values)


def _agent_metadata(agent: Agent) -> dict:
    """Frontmatter as Chroma-compatible scalar metadata (lists flattened)."""
    return {
        "agent_id": agent.agent_id,
        "name": agent.name,
        "domain": agent.domain,
        "tags": _join(agent.tags),
        "autonomy_default": agent.autonomy_default,
        "autonomy_supported": _join(agent.autonomy_supported),
        "triggers": _join(agent.triggers),
        # Absence of triggers is "not specified", not "no triggers" (section 8).
        "triggers_specified": bool(agent.triggers),
    }


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def _reset_collection(client, name: str):
    """Drop ``name`` if it exists, then create it fresh (clean rebuild)."""
    try:
        client.delete_collection(name=name)
    except Exception:
        pass  # didn't exist yet
    return client.create_collection(
        name=name,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": config.DISTANCE_SPACE},
    )


def build_index(agents_dir: str | Path | None = None, chroma_path: str | Path | None = None) -> dict:
    """Rebuild the ChromaDB store from the catalog. Returns a small summary dict.

    Idempotent: safe to re-run; it rebuilds both collections from scratch.
    """
    agents_dir = Path(agents_dir) if agents_dir is not None else config.AGENTS_DIR
    agents = load_agents(agents_dir)

    client = get_client(chroma_path)
    summaries = _reset_collection(client, config.SUMMARY_COLLECTION)
    sections = _reset_collection(client, config.SECTION_COLLECTION)

    n_summaries = 0
    n_sections = 0

    for agent in agents:
        base_meta = _agent_metadata(agent)

        # One coarse agent-summary record per agent.
        summaries.add(
            ids=[agent.agent_id],
            documents=[agent.summary_text()],
            metadatas=[base_meta],
        )
        n_summaries += 1

        # One fine section-chunk record per body section.
        for section, body in agent.sections.items():
            if not body.strip():
                continue
            sections.add(
                ids=[f"{agent.agent_id}::{section}"],
                # Prefix with agent + section so the embedding carries context,
                # which sharpens retrieval for short sections.
                documents=[f"{agent.name} — {section}\n\n{body}"],
                metadatas=[{**base_meta, "section": section}],
            )
            n_sections += 1

    # The catalog just changed: drop the cached collection handles and the
    # router/chatbot name caches so a running process sees the new agents
    # immediately, with no restart (cache invalidation after re-index).
    refresh_catalog_caches()

    return {
        "agents": len(agents),
        "summary_records": n_summaries,
        "section_records": n_sections,
        "chroma_path": str(chroma_path or config.CHROMA_PATH),
    }


if __name__ == "__main__":  # python -m src.index
    stats = build_index()
    print(
        f"Indexed {stats['agents']} agents -> "
        f"{stats['summary_records']} summary + {stats['section_records']} section "
        f"records at {stats['chroma_path']}"
    )
