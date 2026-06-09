"""Catalog loader — parse a single agent `.md` file into structured data.

Splits a Markdown document into its YAML frontmatter (metadata) and its body
sections, returning the ``Agent`` model defined in ``models.py``. Section
headers are normalized and identical across all files, which lets the parser
target each section reliably (PROBLEM_STATEMENT.md sections 3 and 4.1).

This is the first piece in the build order (PROBLEM_STATEMENT.md section 6.1).
"""

# TODO: implement parsing of one `.md` file -> Agent (frontmatter + sections),
# and a helper to load every file under AGENTS_DIR, per PROBLEM_STATEMENT.md
# section 4.1. Handle empty/optional frontmatter fields (e.g. empty `triggers`)
# as "not specified" per section 8.
