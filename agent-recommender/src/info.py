"""Information-lookup path (RAG) — answer a question about a specific agent.

Exposes ``answer_question(query)`` exactly as in PROJECT_HANDOFF.md section 7:

    answer_question(query) -> { "answer": str, "sources": list[Hit], "grounded": bool }

How it works (PROBLEM_STATEMENT.md section 4.4):

1. **Find the agent.** Identify which agent the question is about by name/id
   (``router.find_agent``); fall back to pure retrieval when none is named.
2. **Find the section.** Map attribute words in the question to a section
   header ("inputs" -> ``Inputs``, "hardware" -> ``Deployment``, ...), so
   retrieval can be scoped to the right section where possible.
3. **Retrieve.** ``search_sections`` over the section-chunk records, scoped by a
   metadata ``where`` filter (agent and/or section). If a tight section filter
   returns nothing, widen to the agent, then to the whole catalog.
4. **Answer, grounded strictly.** Hand the retrieved text to the LLM with an
   instruction to answer only from it (and to say so when it can't), with a
   deterministic offline fallback that returns the retrieved section verbatim.
   When the relevant section has no real content (e.g. Deployment is ``TBD`` or
   a section is "not specified"), return ``grounded=False`` and an honest "I
   don't have that information" rather than guessing (PROBLEM_STATEMENT.md
   sections 4.4 and 8).

``search_fn`` is injectable so the path can be tested deterministically against
the section-7 contract without a live store (the working-agreement stub rule).
"""

from __future__ import annotations

import re
from typing import Callable

from . import recommender
from .llm import generate
from .logger import get_logger
from .retriever import Hit, search_sections
from .router import agent_exists, find_agent

log = get_logger(__name__)

INFO_TOP_K = 5  # section-chunk hits to retrieve (matches the §7 default)

# A horizontal rule that brackets the exact prompt in the trace (manager-facing).
_RULE = "─────────────────────────────────"

SearchFn = Callable[..., list[Hit]]


# ---------------------------------------------------------------------------
# Question -> target section
# ---------------------------------------------------------------------------

# Ordered most-specific-first; the first pattern to match picks the section.
# Section names match the headers the indexer stores verbatim.
_SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\binputs?\b|\bwhat .*\bprovide\b", re.IGNORECASE), "Inputs"),
    (re.compile(r"\boutputs?\b|\bproduce|\bdeliver|\breturns?\b", re.IGNORECASE), "Outputs"),
    (re.compile(r"\bautonom(y|ous)\b|\bhuman[- ]in[- ]the[- ]loop\b|\bhitl\b", re.IGNORECASE), "Autonomy Level"),
    (re.compile(r"\btrigger\w*\b|\bwebhook\b|\bhow .*\b(start|invoke|kick off)\b", re.IGNORECASE), "Triggers"),
    (re.compile(r"\bdeploy(ment)?\b|\bhardware\b|\bsoftware\b|\brequirements?\b|\binfrastructure\b|\bhost(ed|ing)?\b", re.IGNORECASE), "Deployment"),
    (re.compile(r"\blimitations?\b|\bconstraints?\b|\bweakness|\bcan'?t\b|\bcannot\b", re.IGNORECASE), "Limitations"),
    (re.compile(r"\boverview\b|\bwhat (does|is) .*\bdo\b|\bwhat can .*\bdo\b|\bpurpose\b|\bsummary\b", re.IGNORECASE), "Overview"),
]

# Definitional phrasings ("what is X", "tell me about X", "describe X", ...) name
# no section, but they're asking what the agent *is* — i.e. its Overview. Checked
# only AFTER the specific-section patterns above, so "what are the inputs" still
# resolves to Inputs; bare definitional questions fall through to Overview.
_DEFINITIONAL_RE = re.compile(
    r"\bwhat(?:'s| is| are)\b|\btell me about\b|\bdescribe\b|\bwho is\b"
    r"|\bexplain\b|\bsummar(?:y|ise|ize)\b|\boverview\b|\babout\b",
    re.IGNORECASE,
)


def detect_section(query: str) -> str | None:
    """Map a question to the section header it's about, or ``None``."""
    text = query or ""
    for pattern, section in _SECTION_PATTERNS:
        if pattern.search(text):
            return section
    if _DEFINITIONAL_RE.search(text):
        return "Overview"
    return None


def _build_where(agent_id: str | None, section: str | None) -> dict | None:
    """Compose a Chroma ``where`` filter from the detected agent/section."""
    clauses = []
    if agent_id:
        clauses.append({"agent_id": agent_id})
    if section:
        clauses.append({"section": section})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


# ---------------------------------------------------------------------------
# Grounding helpers
# ---------------------------------------------------------------------------

_NO_INFO = "I don't have information about that in the agent catalog."

# A response sentinel the LLM is told to emit when the answer isn't in context.
_INSUFFICIENT_RE = re.compile(r"INSUFFICIENT_CONTEXT", re.IGNORECASE)

_SYSTEM = (
    "You answer questions about AI agents using ONLY the provided documentation "
    "excerpts. Do not use outside knowledge and never invent capabilities, "
    "inputs, outputs, or specifications. If the excerpts do not contain the "
    "answer, reply with exactly: INSUFFICIENT_CONTEXT."
)


def _strip_prefix(hit: Hit) -> str:
    """Recover a section's body from a chunk stored as ``name — section\\n\\nbody``."""
    text = hit.text or ""
    if hit.name and hit.section:
        prefix = f"{hit.name} — {hit.section}"
        if text.startswith(prefix):
            return text[len(prefix):].lstrip("\n").strip()
    return text.strip()


def _looks_missing(body: str) -> bool:
    """True when a section body has no real content (TBD / "not specified").

    Handles the known gaps in PROBLEM_STATEMENT.md section 8: Deployment fields
    are ``TBD`` and some Triggers/Limitations are "Not specified in source." The
    check strips the placeholder boilerplate (field labels, ``TBD``, the
    "not specified" phrase, markdown) and treats the section as missing when
    almost nothing substantive remains.
    """
    text = (body or "").strip()
    if not text:
        return True
    low = text.casefold()
    if "tbd" not in low and "not specified" not in low and "not available" not in low:
        return False
    stripped = re.sub(
        r"tbd|not specified in source|not specified|not available"
        r"|\*\*hardware:?\*\*|\*\*software:?\*\*|hardware|software",
        "",
        low,
    )
    stripped = re.sub(r"[*_`|:\-\s.]", "", stripped)
    return len(stripped) < 8


def _missing_message(hit: Hit) -> str:
    """Honest "I don't have that" message naming what's missing."""
    what = (hit.section or "that detail").lower()
    name = hit.name or "this agent"
    return (
        f"I don't have that information. The {name} documentation doesn't "
        f"specify its {what} — it's currently marked TBD / not specified."
    )


def _fallback_answer(hit: Hit, body: str) -> str:
    """Deterministic grounded answer: quote the retrieved section verbatim."""
    label = hit.section or "this"
    name = hit.name or "the agent"
    return f"From the {name} documentation ({label}):\n\n{body}"


def _llm_answer(query: str, hits: list[Hit]) -> str | None:
    """LLM answer grounded in the retrieved chunks; ``None`` if unavailable."""
    context = "\n\n---\n\n".join(
        f"[{h.name} — {h.section}]\n{_strip_prefix(h)}" for h in hits
    )
    prompt = (
        f"Question: {query}\n\nDocumentation excerpts:\n{context}\n\n"
        "Answer the question using ONLY the excerpts above. Be concise."
    )
    # The manager explicitly wants to see the exact prompt (logged at INFO).
    log.info("PROMPT SENT TO LLM:")
    log.info(_RULE)
    log.info("[system instruction]\n%s", _SYSTEM)
    log.info("[user prompt]\n%s", prompt)
    log.info(_RULE)
    response = generate(prompt, system=_SYSTEM)
    log.info("LLM RESPONSE: %s", response if response else "None — using fallback")
    return response


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def answer_question(
    query: str,
    *,
    k: int | None = None,
    use_llm: bool = True,
    search_fn: SearchFn | None = None,
) -> dict:
    """Answer a question about an agent, grounded strictly in retrieved text."""
    log.info("RAG PATH STARTED")
    k = k or INFO_TOP_K
    search_fn = search_fn or search_sections

    # Not-in-catalog gate (Bug 3): if the question names a specific agent that
    # isn't in the catalog, answer honestly and never retrieve — otherwise a
    # stray name token could pull section text from an unrelated agent and we'd
    # answer about the wrong one. No agent list here (it could surface the very
    # name fragment the user typed); the recommendation path owns the listing.
    missing = recommender._looks_like_specific_agent_request(query)
    if missing:
        log.info("AGENT NOT IN CATALOG: %s — answering honestly without retrieval", missing)
        return {
            "answer": (
                f"I don't have an agent called '{missing}' in the catalog. "
                "It may be in development or not yet added."
            ),
            "sources": [],
            "grounded": False,
        }

    agent_id = find_agent(query)
    # Defensive: only trust a find_agent hit that really exists in the catalog.
    if agent_id and not agent_exists(agent_id):
        agent_id = None
    log.info("AGENT IDENTIFIED: %s", agent_id or "none — using retrieval")
    section = detect_section(query)
    log.info("SECTION TARGETED: %s", section or "none")

    # Defense-in-depth: if a named agent is asked about definitionally but no
    # section was detected, scope to Overview rather than risk retrieving an
    # unrelated section and tripping the grounding gate. Guarded on definitional
    # phrasing so genuine missing-info questions are NOT masked — they keep their
    # section (or None) and the gate stays free to fire honestly.
    if agent_id and section is None and _DEFINITIONAL_RE.search(query or ""):
        section = "Overview"

    where = _build_where(agent_id, section)
    log.info("WHERE FILTER BUILT: %s", where)

    hits = search_fn(query, k=k, where=where)
    # A tight section filter can miss; widen to the agent, then the whole store.
    if not hits and section and agent_id:
        hits = search_fn(query, k=k, where={"agent_id": agent_id})
    if not hits and where is not None:
        hits = search_fn(query, k=k, where=None)

    if not hits:
        log.info("GROUNDING CHECK: False — no matching content retrieved")
        return {"answer": _NO_INFO, "sources": [], "grounded": False}

    # Prefer hits in the targeted section; otherwise rank as returned.
    relevant = [h for h in hits if section is None or h.section == section] or hits
    top = relevant[0]
    body = _strip_prefix(top)

    log.debug("RETRIEVED CHUNKS (%d):", len(relevant))
    for h in relevant:
        log.debug("  chunk text: %s", h.text)

    # The grounding gate: if the section we'd answer from has no real content,
    # be honest rather than guess (the TBD / "not specified" case).
    if _looks_missing(body):
        log.info("GROUNDING CHECK: False — section is TBD / not specified / empty")
        message = _missing_message(top)
        log.info("ANSWER (grounded=False): %s", message)
        return {"answer": message, "sources": [top], "grounded": False}

    log.info("GROUNDING CHECK: True — section has real content")

    if use_llm:
        text = _llm_answer(query, relevant)
        if text:
            if _INSUFFICIENT_RE.search(text):
                log.info("ANSWER (grounded=False): LLM reported INSUFFICIENT_CONTEXT")
                return {"answer": _missing_message(top), "sources": relevant, "grounded": False}
            log.info("ANSWER (grounded=True): %s", text)
            return {"answer": text, "sources": relevant, "grounded": True}

    answer = _fallback_answer(top, body)
    log.info("ANSWER (grounded=True): %s", answer)
    return {"answer": answer, "sources": [top], "grounded": True}
