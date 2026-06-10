"""Retriever — query the ChromaDB store with semantic search + metadata filters.

Provides the read side over the two record types built by ``index.py``:

* ``search_agents`` — semantic search over **agent-summary** records for the
  recommendation path, with optional metadata filters the query implies (e.g.
  ``where={"autonomy_default": "L4"}`` for "which agents are fully autonomous")
  — PROBLEM_STATEMENT.md section 4.3.
* ``search_sections`` — scoped retrieval over **section-chunk** records for the
  info-lookup path, filtering to the right ``agent_id`` and, where possible,
  the right ``section`` — PROBLEM_STATEMENT.md section 4.4.

Both return a list of ``Hit`` (the contract in PROJECT_HANDOFF.md section 7),
ordered best-first. Grounded answer generation lives elsewhere; this layer only
retrieves raw records.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .index import get_client, get_section_collection, get_summary_collection


@dataclass
class Hit:
    """One retrieved record (PROJECT_HANDOFF.md section 7 contract)."""

    agent_id: str
    name: str
    text: str
    score: float                       # cosine similarity in [0, 1], higher = closer
    section: str | None = None         # set for section hits, None for agent summaries
    metadata: dict = field(default_factory=dict)


def _to_hits(result) -> list[Hit]:
    """Convert a Chroma ``query`` result into ranked ``Hit`` objects."""
    # Chroma returns a list-per-query; we only ever issue one query at a time.
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    hits: list[Hit] = []
    for i in range(len(ids)):
        meta = metas[i] or {}
        distance = dists[i] if i < len(dists) else None
        # Cosine distance in [0, 2] -> similarity in [-1, 1]; clamp to [0, 1].
        score = 0.0 if distance is None else max(0.0, 1.0 - float(distance))
        hits.append(
            Hit(
                agent_id=str(meta.get("agent_id", "")),
                name=str(meta.get("name", "")),
                text=docs[i] if i < len(docs) else "",
                score=score,
                section=meta.get("section"),
                metadata=meta,
            )
        )
    return hits


def search_agents(query: str, k: int = 3, where: dict | None = None) -> list[Hit]:
    """Semantic search over agent-summary records (the recommendation path).

    ``where`` is a Chroma metadata filter, e.g. ``{"autonomy_default": "L4"}``.
    Returns up to ``k`` ``Hit`` objects ordered best-first.
    """
    client = get_client()
    collection = get_summary_collection(client)
    result = collection.query(
        query_texts=[query],
        n_results=k,
        where=where or None,
    )
    return _to_hits(result)


def search_sections(query: str, k: int = 5, where: dict | None = None) -> list[Hit]:
    """Scoped retrieval over section-chunk records (the info-lookup / RAG path).

    Pass ``where`` to scope to an agent and/or section, e.g.
    ``{"agent_id": "test-data-provisioning"}`` or
    ``{"$and": [{"agent_id": "..."}, {"section": "Inputs"}]}``.
    Returns up to ``k`` ``Hit`` objects ordered best-first.
    """
    client = get_client()
    collection = get_section_collection(client)
    result = collection.query(
        query_texts=[query],
        n_results=k,
        where=where or None,
    )
    return _to_hits(result)
