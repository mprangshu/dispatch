"""Configuration — paths, model names, and retrieval tunables.

Central place for settings referenced across the package so paths, the LLM
model, the embedding model, and retrieval limits/thresholds can be swapped
without touching the rest of the architecture (PROBLEM_STATEMENT.md
sections 2 and 5). Values below are placeholder defaults.
"""

from pathlib import Path

# Filesystem paths.
AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
CHROMA_PATH = Path(__file__).resolve().parent.parent / ".chroma"

# Retrieval tunables.
TOP_K = 4

# Models (configurable / swappable).
MODEL = "gemini-2.5-flash"  # Google Gemini; LLM client reads GEMINI_API_KEY
EMBEDDING_MODEL = "chroma-default"  # ChromaDB's built-in default embedding fn

# TODO: add similarity/score thresholds (e.g. no-match and ambiguity cutoffs)
# once the retriever and edge-case behavior are implemented, per
# PROBLEM_STATEMENT.md sections 4.3 and 4.5.
