"""Indexer — build the persistent ChromaDB store from the `agents/` catalog.

Offline and re-runnable. Scans ``AGENTS_DIR``, parses each file via
``loader.py``, and writes two kinds of records (PROBLEM_STATEMENT.md
section 4.1):

* **Agent-summary records** — one per agent (coarse), embedding a concise
  summary (name + overview + tags). Used by the recommendation path.
* **Section-chunk records** — one per body section (fine), each carrying
  ``agent_id``, ``name``, ``section`` and the frontmatter fields as metadata.
  Used by the info-lookup (RAG) path.

Re-running must rebuild the store cleanly from the current files.
"""

# TODO: implement the rebuild-from-scratch indexer producing both record types
# with metadata, per PROBLEM_STATEMENT.md sections 4.1 and 6.2.
