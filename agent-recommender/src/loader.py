"""Catalog loader — parse a single agent `.md` file into structured data.

Splits a Markdown document into its YAML frontmatter (metadata) and its body
sections, returning the ``Agent`` model defined in ``models.py``. Section
headers are normalized and identical across all files, which lets the parser
target each section reliably (PROBLEM_STATEMENT.md sections 3 and 4.1).

Section bodies are kept as raw markdown — tables are not parsed (the prose is
answered from verbatim at query time). Missing frontmatter keys get sensible
defaults and missing sections are simply absent, so partially-filled files
load without error (PROBLEM_STATEMENT.md section 8).

This is the first piece in the build order (PROBLEM_STATEMENT.md section 6.1).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .models import Agent

# A frontmatter block is the content between a leading `---` and the next `---`.
_FRONTMATTER_RE = re.compile(
    r"\A\s*---\s*\n(?P<frontmatter>.*?)\n---\s*\n?(?P<body>.*)\Z",
    re.DOTALL,
)

# A section header line: "## Section Name". Capture the header text.
_SECTION_RE = re.compile(r"^##\s+(?P<header>.+?)\s*$", re.MULTILINE)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split raw file text into (frontmatter dict, body markdown).

    If there is no frontmatter block, returns an empty dict and the full text
    as the body.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group("frontmatter")
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        # EDGE CASE FIX: malformed YAML frontmatter (e.g. an unterminated string)
        # -> fall back to empty metadata/defaults instead of crashing the load.
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, match.group("body")


def _split_sections(body: str) -> dict[str, str]:
    """Split a markdown body into {header: raw text} on "## " headers.

    Each section's value is the verbatim text under its header (up to the next
    "## " header or end of file), with surrounding blank lines trimmed. Tables
    are preserved as raw markdown.
    """
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for i, match in enumerate(matches):
        header = match.group("header").strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[header] = body[start:end].strip()
    return sections


def _as_list(value) -> list[str]:
    """Coerce a frontmatter value into a list of strings.

    Handles YAML lists, a lone scalar, and missing/None values (-> []).
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def load_agent(path: str | Path) -> Agent:
    """Load and parse a single agent `.md` file into an ``Agent``."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    sections = _split_sections(body)

    return Agent(
        agent_id=str(frontmatter.get("agent_id", path.stem)),
        name=str(frontmatter.get("name", path.stem)),
        domain=str(frontmatter.get("domain", "")),
        tags=_as_list(frontmatter.get("tags")),
        autonomy_default=str(frontmatter.get("autonomy_default", "")),
        autonomy_supported=_as_list(frontmatter.get("autonomy_supported")),
        triggers=_as_list(frontmatter.get("triggers")),
        sections=sections,
        source_path=str(path),
    )


def load_agents(directory: str | Path) -> list[Agent]:
    """Load every `.md` file in ``directory`` into a list of ``Agent``.

    Files are processed in sorted order for deterministic results.
    """
    directory = Path(directory)
    return [load_agent(p) for p in sorted(directory.glob("*.md"))]
