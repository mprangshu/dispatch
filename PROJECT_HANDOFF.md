# Project Handoff & Onboarding — Agent Recommender & Q&A Chatbot

> ⚠️ **Superseded for current state by [`PROJECT_HANDOFF_v2.md`](PROJECT_HANDOFF_v2.md).**
> This file records the original build (Phases 1–5) and its interface contracts,
> which are still accurate. For the latest status — Phase 6 (LLM verified),
> Phase 7 (FastAPI backend), Phase 8 (Streamlit UI in `frontend/`), and the
> 95-test suite — read v2. The contracts in §7 below remain the agreed signatures (note:
> `detect_intent` now defaults to `use_llm=False`).

> Read this **together with `PROBLEM_STATEMENT.md`**. That file is the detailed
> spec (the source of truth for behavior). *This* file is the team-facing layer:
> current state, who owns what, the interface contracts that let us work in
> parallel, and each person's next step.

---

## 1. What we're building (in one paragraph)

A chatbot over a catalog of AI agents (currently four, all in the QA/testing
domain). Each agent is described by one Markdown file. The bot does two things:
**(a) recommendation** — the user describes a need and the bot says which agent
fits and why; **(b) information lookup** — the user asks about an agent ("what's
its autonomy level / inputs / outputs?") and the bot answers, grounded strictly
in that agent's doc. It must never invent facts.

## 2. Architecture & key decisions (already settled)

- **ChromaDB** is the datastore — it holds both embeddings (for semantic search)
  and metadata (for exact filters like `autonomy_default = L3`). No separate
  relational DB.
- **RAG** for the info-lookup path: retrieve the relevant section text, hand it
  to the LLM, generate a grounded answer.
- An **intent layer** sits in front and routes each message to `recommend`,
  `info`, or `clarify`.
- **Two retrieval granularities** stored in Chroma:
  - *agent-summary* records (one per agent) → used by the recommendation path.
  - *section-chunk* records (one per `##` section) → used by the info path.
- **CLI first.** Web/API later; keep core logic decoupled from the interface.

## 3. Current state — all phases complete ✅

**The core build is done: Phases 1–5 are implemented and tested.** The chatbot is
runnable end to end — `python app.py index` then `python app.py`. _(Current state
has since advanced — the LLM is verified live (Phase 6), a FastAPI backend
exists (Phase 7), and a Streamlit UI ships in `frontend/` (Phase 8), with the
suite now at **95 passing**; see
[`PROJECT_HANDOFF_v2.md`](PROJECT_HANDOFF_v2.md). The table below reflects the
Phase 1–5 build.)_ The only open data item is the `TBD` Deployment fields.

| Item | Status |
|------|--------|
| Agent catalog — 4 `.md` files normalized to one template (`agents/`) | ✅ Done |
| `PROBLEM_STATEMENT.md` (the spec) | ✅ Done |
| Repo folder structure scaffolded (stub files with docstrings) | ✅ Done |
| **Phase 1** — `models.py` + `loader.py` + `tests/test_loader.py` | ✅ Done (tested) |
| **Phase 2** — `index.py` + `retriever.py` + `tests/test_indexer.py` | ✅ Done (tested) |
| **Phase 3** — Recommendation path (`recommender.py` + `llm.py` + `tests/test_recommender.py`) | ✅ Done (tested) |
| **Phase 4** — Intent router (`router.py`) + RAG info path (`info.py`) + `tests/test_router.py` & `tests/test_info.py` | ✅ Done (tested) |
| **Phase 5** — Orchestration (`chatbot.py`) + CLI (`app.py`) + `tests/test_chatbot.py` | ✅ Done (tested) |
| All §9 acceptance criteria | ✅ Met (covered by `tests/test_chatbot.py`) |
| Deployment (hardware/software) fields in the docs | ⬜ Still `TBD` — being chased with manager |

## 4. Repo layout

```
agent-recommender/
├── agents/                 # 4 normalized .md agent docs (the input data)
├── src/
│   ├── models.py           # Agent data model            [Phase 1 — done]
│   ├── loader.py           # parse .md -> Agent           [Phase 1 — done]
│   ├── index.py            # build the ChromaDB store     [Phase 2 — done]
│   ├── retriever.py        # query ChromaDB               [Phase 2 — done]
│   ├── recommender.py      # recommend(query) path        [Phase 3 — done]
│   ├── llm.py              # swappable LLM (Gemini) client [Phase 3 — done]
│   ├── router.py           # intent detection             [Phase 4 — done]
│   ├── info.py             # answer_question(query) RAG    [Phase 4 — done]
│   ├── chatbot.py          # handle(message) orchestration [Phase 5 — done]
│   └── config.py           # paths, model names, top_k, thresholds [done]
├── tests/                  # one test_*.py per module + test_chatbot.py (E2E)
├── app.py                  # CLI entry point (index + chat) [Phase 5 — done]
└── requirements.txt
```

## 5. Build order

```
Phase 1 (loader/model)  →  Phase 2 (indexer + retriever)  →  ┬─ Phase 3 (recommend)
                                                             └─ Phase 4 (router + RAG info)
                                                                        ↓
                                                             Phase 5 (orchestrate + CLI + QA)
```

Phases 3 and 4 run in parallel once Phase 2's retriever contract is agreed.

## 6. Team division (5 people)

1. **Data & Knowledge Base** — owns `agents/` + the `.md` template + the
   frontmatter schema (the contract everyone codes against); chasing the missing
   Deployment fields.
2. **Ingestion & Vector Store** — `models.py`, `loader.py`, `index.py`,
   `retriever.py`. The data-access layer everyone else consumes.
3. **Recommendation path** — the "which agent should I use?" feature end to end.
4. **Intent router + RAG info path** — `router.py` + the "answer a question about
   an agent" feature (the LLM/prompt-engineering core).
5. **Orchestration, Interface & QA** — `chatbot.py`, `app.py`, `config.py`, and
   the integration tests that check the acceptance criteria.

## 7. Interface contracts — AGREE THESE BEFORE CODING

These let everyone stub their dependencies and work in parallel. Treat the
signatures as fixed; change them only by team agreement.

**Agent** (produced by Phase 1, consumed by everyone):
```
Agent:
  agent_id: str
  name: str
  domain: str
  tags: list[str]
  autonomy_default: str
  autonomy_supported: list[str]
  triggers: list[str]
  sections: dict[str, str]          # "Overview" -> raw markdown text
  source_path: str
  get_section(name: str) -> str | None
  summary_text() -> str
```

**Retriever** (Phase 2 provides; Phases 3 & 4 consume):
```
search_agents(query: str, k: int = 3, where: dict | None = None) -> list[Hit]
search_sections(query: str, k: int = 5, where: dict | None = None) -> list[Hit]
# `where` is a Chroma metadata filter, e.g. {"autonomy_default": "L3"}
# Hit = { agent_id: str, name: str, section: str | None, text: str,
#         score: float, metadata: dict }
```

**Recommendation path** (Phase 3 provides; Phase 5 consumes):
```
recommend(query: str) -> { agents: list[Hit], explanation: str, ambiguous: bool }
```

**Intent router** (Phase 4 provides; Phase 5 consumes):
```
detect_intent(query: str) -> "recommend" | "info" | "clarify"
```

**Info / RAG path** (Phase 4 provides; Phase 5 consumes):
```
answer_question(query: str) -> { answer: str, sources: list[Hit], grounded: bool }
# grounded=False (and an honest "I don't have that") when the answer isn't in the
# retrieved text — e.g. Deployment fields are still TBD.
```

**Chatbot** (Phase 5 provides):
```
handle(message: str) -> str   # detect_intent -> route -> format reply
```

## 8. Phase log — kept as a record (all phases ✅ DONE)

All five build phases are complete; the prompts below are retained as a record
of how each module was scoped and what its consumer-facing notes are. Each prompt
was scoped to one module, with the rule: **implement only your module; stub your
dependencies against the contracts in section 7; run your own tests.** To pick up
new work (e.g. a web front end, a 5th agent, swapping the embedding model), see
**"Extending the project"** in [ONBOARDING.md](ONBOARDING.md), and still start any
session by reading `PROBLEM_STATEMENT.md` and this file.

### Phase 2 — Ingestion & Vector Store ✅ DONE

`src/index.py` and `src/retriever.py` are implemented and tested
(`tests/test_indexer.py`). Notes for the consuming phases:

- **Build the store:** `python -m src.index` — rebuilds both collections
  (`agent_summaries`, `agent_sections`) cleanly from `agents/`. Writes to
  `.chroma/`. Re-running is safe; no duplicates.
- **Retriever contract is live** exactly as in section 7: `search_agents(query,
  k=3, where=None)` and `search_sections(query, k=5, where=None)` return
  `list[Hit]` ordered best-first. `Hit` is a dataclass with `agent_id`, `name`,
  `text`, `score` (cosine similarity in `[0, 1]`, higher = closer), `section`
  (`None` for agent-summary hits), and `metadata`.
- **Metadata for `where` filters:** frontmatter list fields are flattened to
  comma-joined strings — `tags`, `autonomy_supported` (e.g. `"L1, L2, L3"`),
  `triggers` (`""` when unspecified, with a `triggers_specified` bool). Scalars
  (`agent_id`, `name`, `domain`, `autonomy_default`, `section`) filter directly,
  e.g. `where={"autonomy_default": "L4"}` or
  `where={"$and": [{"agent_id": "..."}, {"section": "Inputs"}]}`.
- **Embeddings:** Chroma's default (local, no API key) — swap in one place via
  `index.get_embedding_function()`.

The original kickoff prompt (kept for reference):
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Phase 1 (models.py, loader.py)
is done. Implement Phase 2 ONLY: src/index.py and src/retriever.py.
- index.py: use load_agents() to read agents/, then build a persistent ChromaDB
  store with TWO record sets — one agent-summary record per agent (embed
  summary_text()) and one section-chunk record per section. Store agent_id, name,
  section, and the frontmatter fields as scalar metadata (flatten list fields like
  tags/triggers/autonomy_supported into Chroma-compatible values). Make re-running
  rebuild the store cleanly.
- retriever.py: implement search_agents() and search_sections() exactly as in
  section 7 of PROJECT_HANDOFF.md, including the `where` metadata filter.
- Add chromadb to requirements.txt. Use Chroma's default embedding function for now.
Write tests that index the real agents/ files and assert that a query returns the
expected agent. Do NOT implement the router, recommendation, chatbot, or CLI.
After implementing, run the tests and show results.
```

### Phase 3 — Recommendation path ✅ DONE

`src/recommender.py` (+ a shared `src/llm.py`) is implemented and tested
(`tests/test_recommender.py` — 10 tests, all green; full suite 27 passed). Notes
for the consuming phases (Phase 5 in particular):

- **`recommend(query)` contract is live** exactly as in section 7:
  `recommend(query) -> {"agents": list[Hit], "explanation": str, "ambiguous": bool}`.
  - One clearly-best agent → `agents=[hit]`, `ambiguous=False`.
  - Several comparable agents → `agents=[shortlist]`, `ambiguous=True`.
  - No fit / out-of-scope → `agents=[]`, `ambiguous=False`, with an honest
    explanation (Phase 5 can append the list of available agents per §4.5).
  - Extra keyword-only args for callers/tests: `recommend(query, *, k=None,
    use_llm=True, search_fn=None)`. `search_fn` is injectable (defaults to
    `retriever.search_agents`) so dependencies can be stubbed against §7.
- **Implied metadata filters:** `recommender.detect_filter(query)` maps
  "fully autonomous" → `{"autonomy_default": "L4"}` and an explicit `L1`–`L4`
  mention directly; it's applied as the retriever `where` filter.
- **Explanations:** generated by the LLM (`src/llm.py`) and grounded in the
  retrieved summaries, with a deterministic offline fallback so the path always
  works and tests need no network. Disable with `use_llm=False`.
- **New shared infra — `src/llm.py`:** a thin, swappable Gemini wrapper
  (`generate(prompt, system=None, model=None) -> str | None`, `available()`).
  Reads `GEMINI_API_KEY` from `.env`, uses `config.MODEL`, and returns `None`
  on any failure so callers degrade gracefully. **Phase 4 should reuse this**
  rather than create a second LLM client.
- **`config.py` thresholds filled** (the previous TODO): `RECOMMEND_TOP_K=3`,
  `NO_MATCH_SCORE=0.15`, `AMBIGUITY_DELTA=0.07`, calibrated against the real
  catalog's default-embedding retrieval scores.

The original kickoff prompt (kept for reference):
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement the recommendation
path ONLY, exposing recommend(query) exactly as in section 7. Use
search_agents() from retriever.py (stub it against the section-7 contract if it's
not merged yet). Rank the best-fitting agent(s), produce a short explanation of
why, support metadata-filtered queries (e.g. "fully autonomous agents" ->
where={"autonomy_default": "L4"}), and handle the ambiguous case with a shortlist.
Do NOT implement the info path, router, or CLI. Write tests for: a clear single
match, an ambiguous case, and a metadata-filtered query. Run the tests and show
results.
```

### Phase 4 — Intent router + RAG info path ✅ DONE

`src/router.py` and `src/info.py` are implemented and tested
(`tests/test_router.py` + `tests/test_info.py` — 32 tests, all green offline).
Notes for Phase 5 (the consumer):

- **`detect_intent(query)` contract is live** exactly as in section 7:
  `detect_intent(query) -> "recommend" | "info" | "clarify"`. Rule-based and
  deterministic by default, with an optional LLM pass (`use_llm=True`, the
  default) that falls back to the rules whenever the LLM is unavailable or
  returns anything other than the three labels. Empty/very-short/vague messages
  classify as `clarify`. Pass `use_llm=False` for deterministic behavior.
- **`answer_question(query)` contract is live** exactly as in section 7:
  `answer_question(query) -> {"answer": str, "sources": list[Hit], "grounded": bool}`.
  It identifies the agent via `router.find_agent` (catalog-driven, no hard-coded
  names) or falls back to retrieval, maps the question to a section header
  (`detect_section`), scopes `search_sections` with a `where` filter, and widens
  the filter if a tight one returns nothing.
- **Grounding gate (§4.4/§8):** when the relevant section has no real content —
  Deployment `TBD`, or "Not specified in source" — it returns `grounded=False`
  with an honest "I don't have that information" and never fabricates. Phase 5
  can surface `grounded` directly in the reply.
- **Extra keyword-only args for callers/tests:** `answer_question(query, *,
  k=None, use_llm=True, search_fn=None)` and `detect_intent(query, *,
  use_llm=True)`. `search_fn` is injectable (defaults to
  `retriever.search_sections`) so dependencies can be stubbed against §7.
- **Reuses `src/llm.py`** (the Phase 3 wrapper) for both the optional intent
  pass and grounded answer generation — no second LLM client, as agreed.
- **New file — `src/info.py`:** the info/RAG path lives here, mirroring how the
  recommendation path lives in `recommender.py`. `chatbot.py` should import
  `answer_question` from `src.info` and `detect_intent` from `src.router`.

The original kickoff prompt (kept for reference):
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement router.py and the
RAG info path ONLY. detect_intent(query) returns "recommend" | "info" | "clarify"
per section 7. answer_question(query) identifies the target agent, uses
search_sections() (stub against the section-7 contract if not merged) to retrieve
the right section(s), then has the LLM answer GROUNDED STRICTLY in retrieved text;
when the info isn't present (e.g. Deployment is TBD) return grounded=False with an
honest "I don't have that information." Do NOT implement recommendation or CLI.
Write tests for: an inputs/outputs question, a missing-data question (must not
hallucinate), and intent classification on a few sample messages. Run and show
results.
```

### Phase 5 — Orchestration, CLI & QA ✅ DONE

`src/chatbot.py` and `app.py` are implemented and tested (`tests/test_chatbot.py`
— 9 tests covering every §9 acceptance criterion; full suite **68 passed**). This
closes the build.

- **`handle(message)` contract is live** exactly as in section 7:
  `handle(message: str) -> str`. It calls `detect_intent`, routes to `recommend`
  / `answer_question` / a clarifying question, and formats one user-facing reply.
  - **recommend** → returns the recommender's explanation; on a no-match it
    appends the list of available agents (§4.5).
  - **info** → returns the grounded answer with a `_Source: <name> — <section>_`
    line; an ungrounded "I don't have that" passes straight through with no
    source line (§4.4/§8).
  - **clarify** (and empty input) → asks one clarifying question and lists what
    the bot can do plus the available agents.
  - Extra keyword-only arg `handle(message, *, use_llm=True)` threads through to
    every path, so the whole chatbot runs deterministically offline. The path
    functions/router are module-level names in `chatbot.py`, so they can be
    monkeypatched in tests.
- **`available_agent_names()`** reads the live catalog (no hard-coded names), so
  a new `.md` file shows up in the edge-case replies automatically.
- **CLI — `app.py`:** `python app.py index` (re)builds the store;
  `python app.py` (or `python app.py chat`) runs the REPL. The REPL checks the
  store exists and points you at `index` instead of crashing; clean exit on
  `exit`/`quit`/Ctrl-D.
- **Package exports:** `from src import handle, recommend, answer_question,
  detect_intent, build_index` — one import surface for the CLI, tests, and any
  future web/API front end.
- **`config.py`** needed no Phase-5 changes (Phase 3 had already filled the
  thresholds); it stays the single place for paths, model names, and tunables.

The original kickoff prompt (kept for reference):
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement chatbot.py, app.py,
and config.py ONLY. handle(message) calls detect_intent() then routes to
recommend() or answer_question() or asks one clarifying question, then formats the
reply. Stub the path functions against the section-7 contracts until they're
merged. app.py is a simple REPL. Then write integration tests covering the
acceptance criteria in PROBLEM_STATEMENT.md section 9 (correct recommendation,
grounded info answer, honest "not available", vague->clarify, and that adding a
new .md + re-index makes it discoverable). Run and show results.
```

### Person 1 — Data & schema (ongoing)
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Audit the four files in agents/
against the template in PROBLEM_STATEMENT.md section 3: confirm identical section
headers, valid frontmatter, and consistent autonomy values. Then fill the
Deployment (Hardware/Software) sections once the manager provides them, keeping
the same template. Do not change any code.
```

## 9. Working agreements

- `PROBLEM_STATEMENT.md` is the source of truth for behavior; this file is for
  state, ownership, and contracts.
- One phase per Claude Code session; don't edit another person's module.
- Stub dependencies against the section-7 contracts so no one is blocked.
- Everyone unit-tests their own module; Person 5 owns end-to-end tests.
- If a contract needs to change, raise it with the team — don't change it locally.
