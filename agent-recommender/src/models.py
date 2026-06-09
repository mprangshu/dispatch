"""Agent data model — the in-memory representation of one catalog `.md` file.

Captures the two layers of an agent document described in
PROBLEM_STATEMENT.md section 3:

* **Frontmatter** (structured/filterable): ``agent_id``, ``name``, ``domain``,
  ``tags``, ``autonomy_default``, ``autonomy_supported``, ``triggers``. These
  become ChromaDB metadata.
* **Body sections** (prose): Overview, Autonomy Level, Inputs, Outputs,
  Triggers, Deployment, Limitations. Section headers are identical across all
  files so a single section can be targeted reliably at query time.

This module defines the schema only; parsing lives in ``loader.py``.
"""

# TODO: define the Agent data model (e.g. a dataclass) carrying the frontmatter
# fields plus a mapping of section-name -> section-text, per PROBLEM_STATEMENT.md
# section 3. Keep it pure data — no I/O, no Chroma concerns.
