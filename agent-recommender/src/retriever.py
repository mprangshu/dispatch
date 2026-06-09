"""Retriever — query the ChromaDB store with semantic search + metadata filters.

Provides the read side over the two record types built by ``index.py``:

* Semantic search over **agent-summary** records for the recommendation path,
  with optional metadata filters the query implies (e.g. filter on
  ``autonomy_default`` for "which agents are fully autonomous") —
  PROBLEM_STATEMENT.md sections 4.3.
* Scoped retrieval over **section-chunk** records for the info-lookup path,
  filtering to the right ``agent_id`` and, where possible, the right
  ``section`` — PROBLEM_STATEMENT.md section 4.4.

Returns raw retrieved records; grounded answer generation lives in
``chatbot.py``.
"""

# TODO: implement summary search (with filters) and section-chunk retrieval
# (agent/section scoped), honoring TOP_K, per PROBLEM_STATEMENT.md
# sections 4.3, 4.4 and 6.3.
