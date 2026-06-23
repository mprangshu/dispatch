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
from functools import lru_cache
from typing import Callable

from . import config, router
from .llm import generate
from .loader import load_agents
from .logger import get_logger
from .retriever import Hit, search_agents

log = get_logger(__name__)

# Brackets the exact prompt in the trace (manager-facing), like the info path.
_RULE = "─────────────────────────────────"

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
# "Not in catalog" detection (the recommendation-path grounding gate)
# ---------------------------------------------------------------------------

# Words that mark a boundary of an agent *name* — determiners, question words,
# verbs, prepositions, and attribute/predicate words. When extracting a name we
# stop at these so we never capture into the predicate of the sentence (Bug D:
# "CI/CD Agent output" must yield "CI/CD", not "CI/CD Agent output").
_NAME_STOP_WORDS = {
    # determiners / pronouns / fillers
    "the", "a", "an", "this", "that", "these", "those", "any", "some", "my",
    "our", "your", "their", "its", "it", "i", "we", "you", "they", "me",
    "anything", "something", "someone", "please", "just", "really",
    # question words
    "what", "which", "who", "whom", "whose", "how", "when", "where", "why",
    # verbs / auxiliaries
    "do", "does", "did", "is", "are", "am", "was", "were", "be", "been", "being",
    "have", "has", "had", "can", "could", "would", "should", "will", "shall",
    "may", "might", "must", "need", "needs", "want", "wants", "looking", "look",
    "find", "get", "use", "using", "make", "build", "create", "tell", "show",
    "give", "recommend", "suggest", "call", "called", "name", "named", "help",
    # prepositions / conjunctions
    "for", "to", "of", "about", "with", "from", "in", "on", "at", "by", "as",
    "and", "or", "but", "there", "here",
    # attribute / predicate words (Bug D)
    "output", "outputs", "input", "inputs", "produce", "produces", "return",
    "returns", "require", "requires", "support", "supports", "trigger",
    "triggers", "deploy", "deployment", "handle", "handles", "provide",
    "provides", "run", "runs", "work", "works", "cost", "costs",
}

# A name token: letters/digits and the few separators that appear in real names
# ("CI/CD", "test-data", "R&D", "v2.0"). Used both to detect and to trim names.
_NAME_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/&.+\-]*$")

# Bare autonomy-level tokens are filter directives, never an agent name.
_AUTONOMY_TOKEN_RE = re.compile(r"^[lL][1-4]$")

# Secondary (Bug 1): a capitalized *capability* noun phrase that names a thing
# without the word "Agent" — e.g. "Performance testing", "Load testing", "Visual
# regression testing", "Chaos engineering". The first token must be Title-/UPPER-
# case and >= 4 chars (so short acronyms like "UI" don't trip it); the second
# token may be lowercase ("testing").
_CAP_PHRASE_RE = re.compile(r"\b([A-Z][A-Za-z]{3,})\s+([A-Za-z]+)\b")

# First words that are ordinary sentence/verb words, not capability nouns.
_COMMON_PHRASE_WORDS = {
    "what", "which", "where", "when", "who", "how", "why", "does", "do", "is",
    "are", "can", "could", "would", "should", "tell", "describe", "explain",
    "show", "give", "find", "make", "build", "create", "automate", "generate",
    "recommend", "suggest", "help", "want", "need", "looking", "please", "the",
    "this", "that", "there", "here", "your", "our", "with", "from", "have",
    "get", "use", "run", "let", "about", "into", "test", "tests", "testing",
    "agent", "agents",
}

# Second words that can't be a noun-phrase tail: articles/prepositions plus the
# predicate words above (so "Generator output" / "Agent output" never fire).
_SECOND_STOPWORDS = {
    "the", "a", "an", "me", "is", "are", "to", "of", "do", "does", "it", "you",
    "with", "for", "that", "this", "my", "our", "your", "and", "or", "in",
    "on", "at", "output", "outputs", "input", "inputs", "produce", "produces",
    "return", "returns", "require", "requires", "support", "supports",
    "trigger", "triggers", "deploy", "use", "handle", "handles", "give",
    "gives", "provide", "provides",
}

# Sentence-opening command / question verbs that can NEVER start an agent name.
# Guards against a capitalised sentence opener being read as a name, e.g.
# "List all the agents" -> "List all" (a catalog-browse request, not an agent).
COMMAND_VERBS = {
    "list", "show", "get", "find", "tell", "give", "display",
    "fetch", "search", "what", "which", "who", "how", "can",
    "could", "would", "is", "are", "do", "does", "have", "help",
}

# Catalog-browsing phrasings — the user wants to see what's available, not a
# specific agent. These route to the catalog list, never the not-in-catalog gate.
_CATALOG_BROWSE_RE = re.compile(
    r"\b(what agents|which agents|all agents|show agents|get agents|list agents"
    r"|what'?s available|what is available)\b",
    re.IGNORECASE,
)
# A browse verb ("list all", "show me all", ...) that, together with an explicit
# mention of "agent(s)", is a catalog-browse request.
_BROWSE_VERB_RE = re.compile(
    r"\b(list all|list the|show all|show me all|show the|see all|see the)\b",
    re.IGNORECASE,
)


def is_catalog_browse_request(query: str) -> bool:
    """Whether the query is a catalog-browse request ("what agents do you have",
    "list all the agents") rather than a question about a specific agent."""
    text = query or ""
    # A query that implies a metadata filter ("which agents are fully autonomous")
    # is a *filtered recommendation*, not a plain browse — let it through.
    if detect_filter(text):
        return False
    if _CATALOG_BROWSE_RE.search(text):
        return True
    if _BROWSE_VERB_RE.search(text) and re.search(r"\bagents?\b", text, re.IGNORECASE):
        return True
    return False


# "called/named (the) X" — capture the region after the verb (Bug B).
_CALLED_RE = re.compile(
    r"\b(?:called|named)\s+(?:the\s+|a\s+|an\s+)?(?P<region>[A-Za-z0-9/&.\- ]+)",
    re.IGNORECASE,
)


def _is_meaningful_name(name: str) -> bool:
    """True if ``name`` is a plausible agent name (not blank, not an L-level, and
    not led by a command/question verb like "list" or "show")."""
    name = (name or "").strip()
    if len(name) < 2:
        return False
    if _AUTONOMY_TOKEN_RE.match(name):
        return False
    tokens = name.split()
    if tokens and tokens[0].casefold() in COMMAND_VERBS:
        return False
    return any(ch.isalnum() for ch in name)


def _tail_name(pre: str) -> str:
    """Extract the agent name sitting at the *end* of ``pre`` (the text just
    before the word "Agent"), walking right-to-left and stopping at the first
    boundary word. e.g. "what does the CI/CD" -> "CI/CD"."""
    tokens = pre.split()
    collected: list[str] = []
    for tok in reversed(tokens):
        clean = tok.strip(".,;:?!\"'()[]")
        if not clean:
            break
        if clean.casefold() in _NAME_STOP_WORDS:
            break
        if not _NAME_TOKEN_RE.match(clean):
            break
        collected.append(clean)
    return " ".join(reversed(collected)).strip()


def _lead_name(region: str) -> str:
    """Extract a name from the *start* of ``region`` (text after "called"),
    stopping at the first boundary word and dropping a trailing "agent"."""
    collected: list[str] = []
    for tok in region.split():
        clean = tok.strip(".,;:?!\"'()[]")
        if not clean or clean.casefold() in _NAME_STOP_WORDS:
            break
        if not _NAME_TOKEN_RE.match(clean):
            break
        collected.append(clean)
    while collected and collected[-1].casefold() in {"agent", "agents"}:
        collected.pop()
    return " ".join(collected).strip()

# Phrasings that ask for the nearest available alternative.
_ASKS_CLOSEST_RE = re.compile(
    r"\b(closest|nearest|similar|alternativ\w*|anything (?:like|similar|else)"
    r"|something (?:like|similar)|close to|instead)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _catalog_vocab() -> tuple[str, ...]:
    """Casefolded agent names + tags (hyphens normalized to spaces), for the
    substring guard that keeps the capability check from firing on real agents."""
    entries: list[str] = []
    try:
        agents = load_agents(config.AGENTS_DIR)
    except Exception:  # pragma: no cover - catalog unreadable -> no guard
        agents = []
    for agent in agents:
        name = agent.name.casefold()
        entries.append(name)
        entries.append(name.replace("-", " "))
        for tag in agent.tags:
            t = str(tag).casefold()
            entries.append(t)
            entries.append(t.replace("-", " "))
    return tuple(entries)


def _detect_uncataloged_capability(text: str) -> str | None:
    """Return a capability-style phrase not present in the catalog, or ``None``."""
    for match in _CAP_PHRASE_RE.finditer(text):
        first, second = match.group(1), match.group(2)
        # A capability noun phrase can't start with a sentence opener / command
        # verb ("List all", "Show me", "What agents").
        if first.casefold() in _COMMON_PHRASE_WORDS or first.casefold() in COMMAND_VERBS:
            continue
        # The tail of a capability noun phrase can't be an article, preposition,
        # verb, or predicate word ("Analyser need", "Generator output").
        if second.casefold() in _SECOND_STOPWORDS or second.casefold() in _NAME_STOP_WORDS:
            continue
        phrase = f"{first} {second}"
        low = phrase.casefold()
        if any(low in entry for entry in _catalog_vocab()):
            continue  # it's part of a real agent name/tag -> normal path
        return phrase
    return None


def asks_for_closest(query: str) -> bool:
    """Whether the query asks for the nearest available alternative."""
    return bool(_ASKS_CLOSEST_RE.search(query or ""))


# Reversed phrasing — the capability follows the word "agent" rather than
# preceding it: "an agent for performance testing", "an agent that does chaos
# engineering", "an agent to handle visual regression".
_AGENT_FOR_RE = re.compile(
    r"agents?\s+(?:for|that\s+does|that\s+handles|to\s+do|to\s+handle|for\s+doing)\s+"
    r"(?P<name>[a-zA-Z][a-zA-Z\s\-/]{2,30})",
    re.IGNORECASE,
)


def _looks_like_specific_agent_request(query: str) -> str | None:
    """Return the unrecognized agent/capability the user seems to want, else
    ``None``.

    Detects when a query names a *specific* agent — explicitly ("... X Agent",
    "anything called the X", "I need the X agent") or as a capability noun phrase
    ("Performance testing") — that isn't in the live catalog. If the named thing
    **is** in the catalog, the normal path should run, so this returns ``None``.
    This is the recommendation-path analogue of the info path's grounding gate:
    we'd rather say "that agent may not exist yet" than recommend a
    loosely-similar agent, answer about the wrong one, or emit a generic no-match.
    """
    text = query or ""

    # A catalog-browse request ("list all the agents", "what agents do you have")
    # names no specific agent — never fire the gate on it.
    if is_catalog_browse_request(text):
        return None

    # 1) "... <name> agent(s) ..." — the name is the tokens immediately before
    #    the word "agent", trimmed at the first boundary word (Bugs B, C1, D).
    match = re.search(r"\b[Aa]gents?\b", text)
    if match:
        name = _tail_name(text[: match.start()])
        if name:
            if router.agent_exists(name):
                return None  # a real catalog agent was named -> normal path
            if _is_meaningful_name(name):
                return name
            # otherwise (e.g. a bare "L1") fall through to the checks below

    # 1b) Reversed phrasing: "an agent for performance testing", "an agent that
    #     does chaos engineering", "an agent to handle visual regression" — the
    #     named capability follows the verb instead of preceding "Agent".
    rev = _AGENT_FOR_RE.search(text)
    if rev:
        name = re.sub(r"\s+", " ", rev.group("name")).strip(" .,;:?!\"'()[]").strip()
        if name:
            if router.agent_exists(name):
                return None  # a real catalog agent/capability -> normal path
            if _is_meaningful_name(name):
                return name

    # 2) "called/named (the) X" with no trailing "Agent" word.
    called = _CALLED_RE.search(text)
    if called:
        name = _lead_name(called.group("region"))
        if name:
            if router.agent_exists(name):
                return None
            if _is_meaningful_name(name):
                return name

    # 3) Capability noun phrase ("Performance testing") with no "agent" word.
    return _detect_uncataloged_capability(text)


def _catalog_agent_names() -> list[str]:
    """Display names of every agent in the live catalog (empty if unreadable)."""
    try:
        return [agent.name for agent in load_agents(config.AGENTS_DIR)]
    except Exception:  # pragma: no cover - catalog unreadable -> no list
        return []


def _not_in_catalog_message(name: str, closest: Hit | None = None) -> str:
    """Honest "that agent isn't here" reply, listing what *is* available and,
    when asked, the closest available alternative."""
    msg = (
        f"I don't have an agent called '{name}' in the catalog. "
        "It may be in development or not yet added. "
        "Here's what's currently available:"
    )
    names = _catalog_agent_names()
    if names:
        msg += "\n\n" + "\n".join(f"- {n}" for n in names)
    if closest is not None:
        snippet = _overview_snippet(closest)
        if snippet:
            msg += f"\n\nThe closest agent we have is **{closest.name}**: {snippet}"
        else:
            msg += f"\n\nThe closest agent we have is **{closest.name}**."
    return msg


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
    log.info("RECOMMENDATION PATH STARTED")
    k = k or config.RECOMMEND_TOP_K
    search_fn = search_fn or search_agents

    # Grounding gate: if the user names a specific agent/capability that isn't in
    # the catalog, say so honestly *before* retrieval rather than recommending a
    # loosely-similar agent or emitting a generic no-match. When they ask for the
    # closest alternative, surface the top semantic match (if it clears the floor).
    missing = _looks_like_specific_agent_request(query)
    if missing:
        closest = None
        if asks_for_closest(query):
            hits = search_fn(query, k=k, where=None)
            if hits and hits[0].score >= config.NO_MATCH_SCORE:
                closest = hits[0]
        log.info("DECISION: requested agent not in catalog — %s", missing)
        return {
            "agents": [],
            "explanation": _not_in_catalog_message(missing, closest),
            "ambiguous": False,
            "not_in_catalog": True,
        }

    where = detect_filter(query)
    log.info("FILTER DETECTED: %s", where or "none")
    hits = search_fn(query, k=k, where=where)

    log.debug("CANDIDATE AGENTS (%d hits):", len(hits))
    for rank, h in enumerate(hits, 1):
        log.debug("  #%d | agent=%s | score=%.4f", rank, h.name, h.score)

    # Nothing came back (e.g. a filter that matched no agent), or — for an
    # unfiltered query — the best hit is too weak to be a real match
    # (out-of-scope). A filter is itself strong evidence of intent, so we trust
    # it and skip the semantic floor when one was applied.
    if not hits or (where is None and hits[0].score < config.NO_MATCH_SCORE):
        log.info("DECISION: no match")
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
        log.info("DECISION: shortlist (%d agents)", len(shortlist))
        return {
            "agents": shortlist,
            "explanation": _explain_shortlist(query, shortlist, use_llm),
            "ambiguous": True,
        }

    log.info("DECISION: single match — %s", top.name)
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
        prompt = (
            f"User need: {query}\n\n"
            f"Recommended agent description:\n{hit.text}\n\n"
            "In one or two sentences, explain why this agent fits the user's "
            "need. Start with the agent's name. Use only the description above."
        )
        log.info("PROMPT SENT TO LLM:")
        log.info(_RULE)
        log.info("[system instruction]\n%s", _SYSTEM)
        log.info("[user prompt]\n%s", prompt)
        log.info(_RULE)
        text = generate(prompt, system=_SYSTEM)
        log.info("LLM RESPONSE: %s", text if text else "None — using fallback")
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
        prompt = (
            f"User need: {query}\n\n"
            f"Candidate agents:\n{blocks}\n\n"
            "Several agents could fit. In one short sentence each, say what each "
            "candidate does, then ask one clarifying question to decide between "
            "them. Use only the descriptions above."
        )
        log.info("PROMPT SENT TO LLM:")
        log.info(_RULE)
        log.info("[system instruction]\n%s", _SYSTEM)
        log.info("[user prompt]\n%s", prompt)
        log.info(_RULE)
        text = generate(prompt, system=_SYSTEM)
        log.info("LLM RESPONSE: %s", text if text else "None — using fallback")
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