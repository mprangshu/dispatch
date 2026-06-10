"""Chatbot orchestration — turn a message into a grounded reply.

Ties the pieces together (PROBLEM_STATEMENT.md sections 4.3-4.5), exposing the
single entry point in PROJECT_HANDOFF.md section 7:

    handle(message: str) -> str   # detect_intent -> route -> format reply

1. Use ``router.detect_intent`` to classify the message
   (``recommend`` / ``info`` / ``clarify``).
2. Dispatch to the matching path:
   * **recommend** — ``recommender.recommend`` returns the best fit (or a
     shortlist) with a short explanation of why (section 4.3).
   * **info** — ``info.answer_question`` runs RAG and returns an answer grounded
     strictly in the retrieved section text (section 4.4).
   * **clarify** — ask one clarifying question (section 4.5).
3. Format a single user-facing string, handling the edge cases (section 4.5):
   * **no match / out of scope** — say nothing clearly fits and list the
     available agents;
   * **ambiguous** — surface the shortlist the recommender produced;
   * **grounding** — pass through the honest "I don't have that information"
     when ``grounded`` is False (e.g. Deployment fields that are "TBD",
     section 8) rather than inventing anything.

The path functions and the router are module-level names so the orchestration
can be unit-tested by stubbing them. Intent detection always uses the
deterministic router; ``use_llm`` is threaded into the recommend/info paths only
(answer + explanation generation), so the whole chatbot still runs
deterministically offline (the LLM degrades to the grounded fallbacks). The CLI
in ``app.py`` is a thin shell over ``handle``.
"""

from __future__ import annotations

from functools import lru_cache

from . import config
from .info import answer_question
from .loader import load_agents
from .recommender import recommend
from .router import detect_intent


# ---------------------------------------------------------------------------
# Catalog helpers (data-driven; nothing is tied to a fixed agent count)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def available_agent_names() -> tuple[str, ...]:
    """Display names of every agent in the catalog, for the edge-case replies.

    Read from the live ``agents/`` directory so adding an `.md` file surfaces it
    here with no code changes (PROBLEM_STATEMENT.md section 9). Returns an empty
    tuple if the catalog can't be read rather than failing the reply.
    """
    try:
        return tuple(agent.name for agent in load_agents(config.AGENTS_DIR))
    except Exception:  # pragma: no cover - catalog unreadable -> no list
        return ()


def _agent_list_block() -> str:
    """A bulleted list of the catalog's agents (or a gentle note if empty)."""
    names = available_agent_names()
    if not names:
        return ""
    return "Available agents:\n" + "\n".join(f"- {name}" for name in names)


# ---------------------------------------------------------------------------
# Per-intent formatting
# ---------------------------------------------------------------------------


def _format_recommendation(result: dict) -> str:
    """Render a ``recommend`` result, listing the catalog on a no-match."""
    explanation = (result.get("explanation") or "").strip()
    if not result.get("agents"):
        # No clear fit / out of scope (section 4.5): be honest and list options.
        block = _agent_list_block()
        return f"{explanation}\n\n{block}".strip() if block else explanation
    return explanation


def _format_info(result: dict) -> str:
    """Render an ``info`` result, attributing the source when grounded."""
    answer = (result.get("answer") or "").strip()
    if not result.get("grounded"):
        # Honest "I don't have that information" — pass straight through.
        return answer
    sources = result.get("sources") or []
    top = sources[0] if sources else None
    if top is not None and getattr(top, "name", ""):
        label = f"{top.name} — {top.section}" if getattr(top, "section", None) else top.name
        return f"{answer}\n\n_Source: {label}_"
    return answer


def _clarify_reply() -> str:
    """Ask one clarifying question and point at what the bot can do (4.5)."""
    block = _agent_list_block()
    prompt = (
        "I'm not sure what you need yet. You can **describe a task** you want to "
        "automate and I'll recommend an agent, or **ask about a specific agent** "
        "(its inputs, outputs, autonomy level, and so on)."
    )
    return f"{prompt}\n\n{block}".strip() if block else prompt


# ---------------------------------------------------------------------------
# Public entry point (PROJECT_HANDOFF.md section 7)
# ---------------------------------------------------------------------------


def handle(message: str, *, use_llm: bool = True) -> str:
    """Detect intent, route to the matching path, and format a grounded reply.

    Intent is classified by the deterministic router (no API call). ``use_llm``
    is passed to the recommend/info paths for answer/explanation generation, and
    each falls back to its grounded, rule-based behavior when the LLM is
    unavailable, so the whole chatbot can still run deterministically offline.
    """
    text = (message or "").strip()
    if not text:
        return _clarify_reply()

    # Intent detection always uses the deterministic router — it's accurate on
    # the catalog's phrasing and costs no API call. ``use_llm`` is reserved for
    # the answer/explanation generation in the paths below, which halves the
    # number of LLM calls per message.
    intent = detect_intent(text)

    if intent == "recommend":
        return _format_recommendation(recommend(text, use_llm=use_llm))
    if intent == "info":
        return _format_info(answer_question(text, use_llm=use_llm))
    return _clarify_reply()
