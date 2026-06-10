"""Recommendation path — "which agent should I use?" (PROBLEM_STATEMENT.md 4.3).

Exposes ``recommend(query)`` exactly as in PROJECT_HANDOFF.md section 7:

    recommend(query) -> { "agents": list[Hit], "explanation": str, "ambiguous": bool }

How it works:

1. **Implied metadata filters.** If the query implies a structured constraint
   (e.g. "which agents are *fully autonomous*" -> ``autonomy_default == "L4"``),
   turn it into a Chroma ``where`` filter so retrieval is scoped exactly.
2. **Semantic ranking.** Run ``search_agents`` over the agent-summary records
   and rank best-first.
3. **Decide single vs. shortlist.** One clearly-best agent -> return it with a
   short "why". Several comparably-good agents -> return a shortlist and set
   ``ambiguous=True`` (PROBLEM_STATEMENT.md section 4.5). Nothing fits (or an
   out-of-scope query) -> empty list with an honest message.
4. **Explain.** Use the LLM to write a concise, grounded explanation from the
   retrieved summaries, falling back to a deterministic template when the LLM is
   unavailable (so the path always works and stays testable offline).

Thresholds live in ``config.py`` (``NO_MATCH_SCORE``, ``AMBIGUITY_DELTA``).
``search_fn`` is injectable to keep tests fast and deterministic and to honor
the "stub your dependencies against the section-7 contract" working agreement.
"""

from __future__ import annotations

import re
from typing import Callable

from . import config
from .llm import generate
from .retriever import Hit, search_agents

# ---------------------------------------------------------------------------
# Query -> implied metadata filter
# ---------------------------------------------------------------------------

# An explicit autonomy level mentioned in the query, e.g. "an L3 agent".
_AUTONOMY_LEVEL_RE = re.compile(r"\bL([1-4])\b", re.IGNORECASE)

# Phrasings that imply maximum autonomy -> the highest level in the catalog (L4).
_FULLY_AUTONOMOUS_RE = re.compile(
    r"\b(fully|completely|totally)[\s-]*(autonomous|automated|automatic)\b"
    r"|\bno human\b|\bwithout (a |any )?human\b|\bhands[\s-]?off\b",
    re.IGNORECASE,
)


def detect_filter(query: str) -> dict | None:
    """Map a query to a Chroma metadata ``where`` filter, or ``None``.

    Currently recognizes autonomy constraints (the structured field the catalog
    exposes for filtering, PROBLEM_STATEMENT.md section 4.3). "Fully autonomous"
    maps to the highest level (``L4``); an explicit ``L1``-``L4`` maps directly.
    """
    if _FULLY_AUTONOMOUS_RE.search(query):
        return {"autonomy_default": "L4"}
    match = _AUTONOMY_LEVEL_RE.search(query)
    if match:
        return {"autonomy_default": f"L{match.group(1)}"}
    return None


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

SearchFn = Callable[..., list[Hit]]


def recommend(
    query: str,
    *,
    k: int | None = None,
    use_llm: bool = True,
    search_fn: SearchFn | None = None,
) -> dict:
    """Recommend the best-fitting agent(s) for ``query`` (handoff section 7)."""
    k = k or config.RECOMMEND_TOP_K
    search_fn = search_fn or search_agents
    where = detect_filter(query)
    hits = search_fn(query, k=k, where=where)

    # Nothing came back (e.g. a filter that matched no agent), or — for an
    # unfiltered query — the best hit is too weak to be a real match
    # (out-of-scope). A filter is itself strong evidence of intent, so we trust
    # it and skip the semantic floor when one was applied.
    if not hits or (where is None and hits[0].score < config.NO_MATCH_SCORE):
        return {
            "agents": [],
            "explanation": _no_match_explanation(where),
            "ambiguous": False,
        }

    top = hits[0]
    # Shortlist: hits close to the top that are themselves strong enough to
    # suggest. More than one -> the choice is genuinely ambiguous.
    shortlist = [
        h
        for h in hits
        if h.score >= config.NO_MATCH_SCORE
        and (top.score - h.score) <= config.AMBIGUITY_DELTA
    ]

    if len(shortlist) > 1:
        return {
            "agents": shortlist,
            "explanation": _explain_shortlist(query, shortlist, use_llm),
            "ambiguous": True,
        }

    return {
        "agents": [top],
        "explanation": _explain_single(query, top, use_llm),
        "ambiguous": False,
    }


# ---------------------------------------------------------------------------
# Explanations (LLM with a deterministic, grounded fallback)
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You help a user choose the right AI agent from a fixed catalog. Explain "
    "concisely and only from the agent description(s) provided. Never invent "
    "capabilities, inputs, or outputs that are not in the text."
)


def _overview_snippet(hit: Hit, limit: int = 200) -> str:
    """Pull a short overview snippet out of a summary ``Hit``'s text.

    Summary records are ``name`` + Overview + a trailing ``Tags:`` line; strip
    those framing lines and trim to a sentence-ish snippet for the fallback.
    """
    lines = [ln for ln in (hit.text or "").splitlines() if not ln.startswith("Tags:")]
    body = "\n".join(lines).strip()
    if hit.name and body.startswith(hit.name):
        body = body[len(hit.name):].strip()
    snippet = body.split("\n\n")[0].strip().replace("\n", " ")
    if len(snippet) > limit:
        snippet = snippet[:limit].rsplit(" ", 1)[0] + "…"
    return snippet


def _explain_single(query: str, hit: Hit, use_llm: bool) -> str:
    """One-agent explanation: LLM if available, else a grounded template."""
    if use_llm:
        text = generate(
            f"User need: {query}\n\n"
            f"Recommended agent description:\n{hit.text}\n\n"
            "In one or two sentences, explain why this agent fits the user's "
            "need. Start with the agent's name. Use only the description above.",
            system=_SYSTEM,
        )
        if text:
            return text

    parts = [f"I'd recommend **{hit.name}**."]
    snippet = _overview_snippet(hit)
    if snippet:
        parts.append(snippet)
    tags = hit.metadata.get("tags")
    if tags:
        parts.append(f"(Relevant focus: {tags}.)")
    return " ".join(parts)


def _explain_shortlist(query: str, shortlist: list[Hit], use_llm: bool) -> str:
    """Shortlist explanation when several agents fit comparably well."""
    if use_llm:
        blocks = "\n\n---\n\n".join(f"{h.name}:\n{h.text}" for h in shortlist)
        text = generate(
            f"User need: {query}\n\n"
            f"Candidate agents:\n{blocks}\n\n"
            "Several agents could fit. In one short sentence each, say what each "
            "candidate does, then ask one clarifying question to decide between "
            "them. Use only the descriptions above.",
            system=_SYSTEM,
        )
        if text:
            return text

    lines = ["A few agents could fit — could you tell me a bit more about your goal?"]
    for h in shortlist:
        snippet = _overview_snippet(h, limit=120)
        lines.append(f"- **{h.name}**: {snippet}" if snippet else f"- **{h.name}**")
    return "\n".join(lines)


def _no_match_explanation(where: dict | None) -> str:
    """Honest message when nothing fits (PROBLEM_STATEMENT.md section 4.5)."""
    if where:
        return (
            "No agent in the catalog matches that filter. "
            "Try describing the task you want to automate instead."
        )
    return (
        "I couldn't find an agent that clearly fits that request. "
        "Try describing the testing task you want to automate."
    )