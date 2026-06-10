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

# Chroma collection names (one per retrieval granularity, built by index.py).
SUMMARY_COLLECTION = "agent_summaries"   # coarse: one record per agent
SECTION_COLLECTION = "agent_sections"    # fine: one record per body section

# Cosine space keeps distances in [0, 2] so similarity = 1 - distance is well
# defined; set on each collection at index time and used to score retrieval.
DISTANCE_SPACE = "cosine"

# Retrieval tunables.
TOP_K = 4

# Models (configurable / swappable).
MODEL = "gemini-2.5-flash"  # Google Gemini; LLM client reads GEMINI_API_KEY
EMBEDDING_MODEL = "chroma-default"  # ChromaDB's built-in default embedding fn

# Recommendation-path tunables (PROBLEM_STATEMENT.md sections 4.3, 4.5).
# Calibrated against the default-embedding scores of the current catalog:
# clear matches score ~0.5-0.8 with a wide gap to the runner-up, while
# out-of-scope queries top out below ~0.1.
RECOMMEND_TOP_K = 3       # agent-summary hits to retrieve for a recommendation
NO_MATCH_SCORE = 0.15     # top hit below this (and no filter) -> "no clear fit"
AMBIGUITY_DELTA = 0.07    # a runner-up within this of the top -> show a shortlist
