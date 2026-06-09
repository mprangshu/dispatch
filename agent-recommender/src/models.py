"""Agent data model — the in-memory representation of one catalog `.md` file.

Captures the two layers of an agent document described in
PROBLEM_STATEMENT.md section 3:

* **Frontmatter** (structured/filterable): ``agent_id``, ``name``, ``domain``,
  ``tags``, ``autonomy_default``, ``autonomy_supported``, ``triggers``. These
  become ChromaDB metadata.
* **Body sections** (prose): Overview, Autonomy Level, Inputs, Outputs,
  Triggers, Deployment, Limitations. Section headers are identical across all
  files so a single section can be targeted reliably at query time.

This module defines the schema only; parsing lives in ``loader.py``. List
fields are kept as lists here — flattening for ChromaDB metadata is the
indexer's job later (PROBLEM_STATEMENT.md section 4.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Agent:
    """One agent loaded from a catalog `.md` file (frontmatter + sections)."""

    agent_id: str
    name: str
    domain: str
    tags: list[str] = field(default_factory=list)
    autonomy_default: str = ""
    autonomy_supported: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)  # may be empty
    sections: dict[str, str] = field(default_factory=dict)  # header -> raw body
    source_path: str = ""

    def get_section(self, name: str) -> str | None:
        """Return a section's raw text by header name, case-insensitively.

        e.g. ``get_section("Autonomy Level")``. Returns ``None`` when the
        section is absent (PROBLEM_STATEMENT.md section 4.4 — tolerate missing
        sections rather than erroring).
        """
        target = name.strip().casefold()
        for header, body in self.sections.items():
            if header.strip().casefold() == target:
                return body
        return None

    def summary_text(self) -> str:
        """Concise text used later as the agent-summary embedding record.

        Combines name + Overview section + tags, per the recommendation-path
        record described in PROBLEM_STATEMENT.md section 4.1.
        """
        parts = [self.name]
        overview = self.get_section("Overview")
        if overview:
            parts.append(overview.strip())
        if self.tags:
            parts.append("Tags: " + ", ".join(self.tags))
        return "\n\n".join(parts)
