"""Agent Recommender & Q&A Chatbot — core package.

Houses the data model, catalog loader, ChromaDB indexer/retriever, intent
router, and the orchestrating chatbot. The CLI in ``app.py`` is a thin shell
over this package so the core logic stays decoupled from the interface
(see PROBLEM_STATEMENT.md sections 5 and 7).

The public surface mirrors the PROJECT_HANDOFF.md section-7 contracts so
callers (the CLI, a future web front end, tests) import from one place:
``handle`` (orchestration), ``recommend`` / ``answer_question`` /
``detect_intent`` (the paths), and ``build_index`` (catalog ingestion).
"""

from .chatbot import handle
from .index import build_index
from .info import answer_question
from .recommender import recommend
from .router import detect_intent

__all__ = [
    "handle",
    "recommend",
    "answer_question",
    "detect_intent",
    "build_index",
]
