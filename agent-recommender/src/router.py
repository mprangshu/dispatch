"""Intent router — classify each incoming message before routing it.

Classifies a user message into one of three intents
(PROBLEM_STATEMENT.md section 4.2):

* ``recommend`` — the user describes a need and wants a fitting agent.
* ``info`` — the user asks a question about a specific agent.
* ``clarify`` — the message is too vague to act on.

Classification is rule-based and deterministic by default (fast, offline,
testable), with an optional LLM pass in front for fuzzier phrasing
(PROBLEM_STATEMENT.md section 2 — the LLM is used for intent detection). The
LLM degrades gracefully: when it's unavailable or returns something unexpected,
the rules decide, so the router always works without a network.

Agent names are read from the live catalog (via ``loader``) rather than
hard-coded, so adding an `.md` file makes its name recognizable here with no
code changes (PROBLEM_STATEMENT.md section 9). Pure classification only — the
recommendation / RAG paths are dispatched by ``chatbot.py``.
"""

from __future__ import annotations

import re
from functools import lru_cache

from . import config
from .llm import generate
from .loader import load_agents

# ---------------------------------------------------------------------------
# Agent-name detection (data-driven from the catalog)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _agent_terms() -> tuple[tuple[str, str], ...]:
    """``(search_term, agent_id)`` pairs for spotting an agent named in text.

    Built from the current catalog so nothing is tied to a fixed agent count.
    Each agent contributes a few distinctive variants (full name, the name
    without a trailing "Agent", the ``agent_id``, and the id with hyphens as
    spaces). Tiny/ambiguous terms are dropped, and longer terms are tried first
    so the most specific match wins.
    """
    terms: list[tuple[str, str]] = []
    try:
        agents = load_agents(config.AGENTS_DIR)
    except Exception:  # pragma: no cover - catalog unreadable -> no name hints
        agents = []
    for agent in agents:
        name = agent.name.strip()
        variants = {
            name.casefold(),
            re.sub(r"\s+agent$", "", name, flags=re.IGNORECASE).strip().casefold(),
            agent.agent_id.casefold(),
            agent.agent_id.replace("-", " ").casefold(),
        }
        for variant in variants:
            if len(variant) >= 4:  # avoid matching short, ambiguous tokens
                terms.append((variant, agent.agent_id))
    terms.sort(key=lambda t: len(t[0]), reverse=True)
    return tuple(terms)


def find_agent(query: str) -> str | None:
    """Return the ``agent_id`` named in ``query``, or ``None``.

    A whole-phrase substring match on the catalog-derived terms; used to spot
    "info" questions about a specific agent and to scope RAG retrieval.
    """
    text = (query or "").casefold()
    for term, agent_id in _agent_terms():
        if term in text:
            return agent_id
    return None


# ---------------------------------------------------------------------------
# Rule-based intent signals
# ---------------------------------------------------------------------------

# Phrasings that describe a need / ask for a fitting agent across the catalog.
_RECOMMEND_RE = re.compile(
    r"\b(recommend|suggest|which agents?|what agents?|best agent|right agent"
    r"|agent (for|that|to)|i want|i need|i'?m looking|looking for|help me"
    r"|how (do|can) i|is there an agent|fully autonomous)\b",
    re.IGNORECASE,
)

# Attribute words that signal a question about an agent's documented details.
_INFO_ATTR_RE = re.compile(
    r"\b(autonomy|autonomous|inputs?|outputs?|triggers?|webhook|deploy(?:ment)?"
    r"|hardware|software|requirements?|limitations?|what does|what is|what are"
    r"|what'?s|tell me about|how does|does it)\b",
    re.IGNORECASE,
)

# Is the message phrased as a question at all?
_QUESTIONY_RE = re.compile(
    r"\?|^\s*(what|which|who|how|does|do|is|are|can|list|tell)\b",
    re.IGNORECASE,
)

# A task verb that marks a described need even without explicit "I want/need".
_TASK_RE = re.compile(
    r"\b(automat\w*|generat\w*|creat\w*|provision\w*|analy\w*|refin\w*"
    r"|extract\w*|test\w*|script\w*|build\w*|writ\w*|scor\w*)\b",
    re.IGNORECASE,
)


def _classify_rules(text: str) -> str:
    """Deterministic intent classification from the signals above."""
    # Naming a specific agent is a strong "asking about that agent" signal.
    if find_agent(text):
        return "info"

    wants_recommend = bool(_RECOMMEND_RE.search(text))
    asks_info = bool(_INFO_ATTR_RE.search(text)) and bool(_QUESTIONY_RE.search(text))

    if wants_recommend and not asks_info:
        return "recommend"
    if asks_info and not wants_recommend:
        return "info"
    if wants_recommend and asks_info:
        # e.g. "which agent has the highest autonomy" — a cross-catalog ask.
        return "recommend"

    # No strong signal either way.
    if len(re.findall(r"\w+", text)) < 3:
        return "clarify"
    if _TASK_RE.search(text):
        return "recommend"
    return "clarify"


# ---------------------------------------------------------------------------
# Optional LLM classification (front of the rules; falls back on anything odd)
# ---------------------------------------------------------------------------

_LLM_SYSTEM = (
    "You classify a user's message to an AI-agent assistant into exactly one "
    "intent. Reply with ONLY one lowercase word:\n"
    "- recommend: the user describes a task/need and wants a fitting agent.\n"
    "- info: the user asks a question about a specific agent's details.\n"
    "- clarify: the message is too vague to act on.\n"
    "Output only the single word."
)

_VALID = {"recommend", "info", "clarify"}


def _classify_llm(text: str) -> str | None:
    """Ask the LLM for an intent label; ``None`` if unavailable/unparseable."""
    out = generate(f"Message: {text}\n\nIntent:", system=_LLM_SYSTEM)
    if not out:
        return None
    label = out.strip().split()[0].strip().lower().strip(".")
    return label if label in _VALID else None


def detect_intent(query: str, *, use_llm: bool = False) -> str:
    """Classify ``query`` as ``recommend`` | ``info`` | ``clarify``.

    The deterministic rules are the default (``use_llm=False``): they're fast,
    free, offline, and accurate on the catalog's phrasing, so intent detection
    costs no API calls. Pass ``use_llm=True`` to opt into an LLM pass in front
    for fuzzier wording; even then its result is only trusted when it's one of
    the three valid labels, otherwise the rules decide.
    """
    text = (query or "").strip()
    if not text:
        return "clarify"
    if use_llm:
        label = _classify_llm(text)
        if label is not None:
            return label
    return _classify_rules(text)
