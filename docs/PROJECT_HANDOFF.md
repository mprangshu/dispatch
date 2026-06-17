# Project Handoff — Agent Recommender & Q&A Chatbot

> The team-facing **state** doc: current status, the phase log, ownership, and the
> working agreements. Read alongside [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md)
> (the behavior spec). This file merges the original phase-1–5 handoff and the
> later "v2" (LLM activation → API → UI) handoff into one current record.
>
> This doc does **not** restate the things that now have a single home:
> - **Interface contracts / signatures** → [CONTRACTS.md](CONTRACTS.md)
> - **Architecture & repo layout** → [ARCHITECTURE.md](ARCHITECTURE.md)
> - **Message flow** → [DATA_FLOW.md](DATA_FLOW.md)
> - **Setup / run / demo** → [INSTALL.md](INSTALL.md) and [RUNBOOK.md](RUNBOOK.md)

---

## 1. What we're building (one paragraph)

A chatbot over a catalog of AI agents (currently eight, all QA/testing). Each agent
is described by one Markdown file. The bot does two things: **(a) recommendation**
— the user describes a need and the bot says which agent fits and why; **(b) info
lookup** — the user asks about an agent and the bot answers, grounded strictly in
that agent's doc. It must never invent facts.

## 2. Current status

**Complete — Phases 1–8 implemented and tested (101 passing): the core, CLI, HTTP
API, and Streamlit web UI are all built. The one open data item is the `TBD`
Deployment fields.**

| Area | State |
|------|-------|
| Agent catalog — 8 `.md` files normalized to one template | ✅ Done |
| Phase 1 — `models.py` + `loader.py` (+ tests) | ✅ Done |
| Phase 2 — `index.py` + `retriever.py` (+ tests) | ✅ Done |
| Phase 3 — recommendation path `recommender.py` + shared `llm.py` (+ tests) | ✅ Done |
| Phase 4 — intent router `router.py` + RAG info path `info.py` (+ tests) | ✅ Done |
| Phase 5 — orchestration `chatbot.py` + CLI `app.py` (+ E2E tests) | ✅ Done |
| Phase 6 — live-LLM activation & verification (`scripts/verify_llm.py`, mocked `tests/test_llm.py`) | ✅ Done |
| Phase 7 — FastAPI backend `api.py` (+ `tests/test_api.py`) | ✅ Done |
| Phase 8 — Streamlit UI `frontend/` over the API (+ `frontend/tests/test_ui.py`) | ✅ Done |
| Hardening — cached Chroma client/embedding (`store.py`), cache invalidation after re-index, `scripts/watch_agents.py` auto-reindexer (+ `tests/test_store.py`) | ✅ Done |
| Observability — structured pipeline logging (`src/logger.py`): console step-trace + `logs/agent_chatbot.log`, no secrets (+ `tests/test_logging.py`) | ✅ Done |
| Test suite | ✅ 101 passing (deterministic/mocked; CI needs no key) |
| Deployment (hardware/software) doc fields | ⬜ Still `TBD` — info path correctly answers "not available" until filled |

## 3. Build order (how the phases depend)

```
Phase 1 (loader/model) → Phase 2 (indexer + retriever) → ┬─ Phase 3 (recommend)
                                                          └─ Phase 4 (router + RAG info)
                                                                     ↓
                                              Phase 5 (orchestrate + CLI + QA)
                                                                     ↓
              Phase 6 (activate + verify LLM) → Phase 7 (FastAPI) → Phase 8 (Streamlit UI)
```

Phases 3 and 4 ran in parallel once Phase 2's retriever contract was agreed.
Phases 6–8 are "no new core logic": activate/verify the existing LLM wrapper, then
wrap the unchanged core in HTTP, then a UI over that. Do them in order — get the
LLM behaving correctly *before* exposing it over HTTP, and a working API *before*
building a UI against it.

## 4. Team division (5 people)

1. **Data & Knowledge Base** — owns `agents/` + the `.md` template + the
   frontmatter schema (the contract everyone codes against); chasing the missing
   Deployment fields. (Schema: [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md).)
2. **Ingestion & Vector Store** — `models.py`, `loader.py`, `index.py`,
   `retriever.py`. The data-access layer everyone else consumes.
3. **Recommendation path** — the "which agent should I use?" feature end to end.
4. **Intent router + RAG info path** — `router.py` + the "answer a question about
   an agent" feature (the prompt-engineering core).
5. **Orchestration, Interface & QA** — `chatbot.py`, `app.py`, `api.py`,
   `config.py`, and the integration tests covering the acceptance criteria.

## 5. Phase log (record of how each module was scoped)

Each phase was one focused session with the rule: **implement only your module;
stub your dependencies against the [contracts](CONTRACTS.md); run your own tests.**
The original kickoff prompts are kept verbatim as a record.

### Phase 1 — Loader & model ✅
`src/models.py` + `src/loader.py`. Parse a `.md` into an `Agent` (frontmatter +
sections); lists stay lists (flattening is the indexer's job). Tested against the
real catalog.

### Phase 2 — Ingestion & Vector Store ✅
`src/index.py` + `src/retriever.py` (+ shared `src/store.py`). Build two
collections (`agent_summaries`, `agent_sections`) cleanly from `agents/`;
re-running rebuilds with no duplicates. The retriever exposes `search_agents` /
`search_sections` (see [CONTRACTS.md](CONTRACTS.md)). The Chroma client, embedding
function, and collection handles are cached process-level singletons in
`store.py`; embeddings use Chroma's default (local, no key), swappable in one place
via `store.get_embedding_function()`. `build_index()` calls
`store.refresh_catalog_caches()` so a running process sees catalog changes after a
re-index without a restart.

```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Phase 1 (models.py, loader.py)
is done. Implement Phase 2 ONLY: src/index.py and src/retriever.py.
- index.py: use load_agents() to read agents/, then build a persistent ChromaDB
  store with TWO record sets — one agent-summary record per agent (embed
  summary_text()) and one section-chunk record per section. Store agent_id, name,
  section, and the frontmatter fields as scalar metadata (flatten list fields).
  Make re-running rebuild the store cleanly.
- retriever.py: implement search_agents() and search_sections() exactly as in the
  contract, including the `where` metadata filter.
- Add chromadb to requirements.txt. Use Chroma's default embedding function.
Write tests that index the real agents/ files and assert a query returns the
expected agent. Do NOT implement the router, recommendation, chatbot, or CLI.
```

### Phase 3 — Recommendation path ✅
`src/recommender.py` (+ shared `src/llm.py`). `recommend(query)` ranks the
best-fitting agent(s), explains why (LLM with deterministic fallback), supports
implied metadata filters ("fully autonomous" → `L4`), and handles the ambiguous
case with a shortlist. `config.py` thresholds were calibrated here
(`RECOMMEND_TOP_K=3`, `NO_MATCH_SCORE=0.15`, `AMBIGUITY_DELTA=0.07`).

```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement the recommendation
path ONLY, exposing recommend(query) per the contract. Use search_agents() (stub
it if not merged). Rank the best-fitting agent(s), produce a short explanation,
support metadata-filtered queries, and handle the ambiguous case with a shortlist.
Do NOT implement the info path, router, or CLI. Write tests for: a clear single
match, an ambiguous case, and a metadata-filtered query.
```

### Phase 4 — Intent router + RAG info path ✅
`src/router.py` + `src/info.py`. `detect_intent` is rule-based and deterministic
by default; `answer_question` identifies the agent, maps the question to a section,
retrieves scoped chunks, and answers grounded — returning `grounded=False` with an
honest message when the section is `TBD`/empty. Reuses the Phase-3 `llm.py`.

```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement router.py and the RAG
info path ONLY. detect_intent(query) returns recommend|info|clarify.
answer_question(query) identifies the target agent, uses search_sections() (stub
if not merged), then answers GROUNDED STRICTLY in retrieved text; when info isn't
present (e.g. Deployment TBD) return grounded=False with an honest message. Do NOT
implement recommendation or CLI. Write tests for: an inputs/outputs question, a
missing-data question (no hallucination), and intent classification.
```

### Phase 5 — Orchestration, CLI & QA ✅
`src/chatbot.py` + `app.py`. `handle(message)` routes intent → path → one reply,
with edge cases (no-match lists the catalog; grounded info gets a source line;
ungrounded passes through; clarify asks one question). `tests/test_chatbot.py`
covers every §9 acceptance criterion.

```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement chatbot.py, app.py,
and config.py ONLY. handle(message) calls detect_intent() then routes to
recommend()/answer_question()/a clarifying question, then formats the reply. Stub
the path functions until merged. app.py is a simple REPL. Write integration tests
covering the §9 acceptance criteria.
```

### Phase 6 — LLM activation & verification ✅
The LLM wrapper already existed (Phase 3); this phase **activated and verified**
the live path — it did not author it. Added `scripts/verify_llm.py` (an LLM on/off
A/B printout) and mocked guardrail tests (`tests/test_llm.py`) proving the
grounding gate holds with the LLM on. Also made `detect_intent` default to the
deterministic router so `handle()` makes ≤1 LLM call per turn. **The critical
property:** with an empty/`TBD` section, `answer_question(...)["grounded"]` is
`False` *regardless* of what the LLM returns — no fabricated spec can leak.

```
Read PROBLEM_STATEMENT.md, ONBOARDING.md, and PROJECT_HANDOFF.md. The core
(1–5) is complete and src/llm.py already wraps Gemini. Do PHASE 6 ONLY: activate
and verify the live LLM path. Do NOT change any contract, the deterministic
fallbacks, or existing tests' behavior.
1. Confirm .env loading and llm.available()/generate() behavior (None on failure,
   never raises).
2. Add scripts/verify_llm.py: for a recommend query, an info query with real
   content, and a TBD query, print handle(use_llm=True) vs handle(use_llm=False)
   side by side.
3. Add MOCKED guardrail tests (monkeypatch llm.generate, no key needed): LLM text
   is used; None falls back; CRITICAL: empty/TBD sections → grounded=False
   regardless of LLM output.
Keep all existing tests green.
```

### Phase 7 — FastAPI backend ✅
`api.py` exposes `POST /chat`, `GET /agents`, `GET /health` over the **unchanged**
`src` core, CORS open. `tests/test_api.py` covers all three (and CORS) with
`use_llm=False`. Endpoint shapes: [API_REFERENCE.md](API_REFERENCE.md).

```
Read PROBLEM_STATEMENT.md, ONBOARDING.md, and PROJECT_HANDOFF.md. Phase 6 is done.
Do PHASE 7 ONLY: a FastAPI backend wrapping the existing core. Do NOT modify src/
and do NOT break the CLI.
Create agent-recommender/api.py: POST /chat {message, use_llm=true} -> {reply}
(returns handle(...)); GET /agents -> [{agent_id, name, domain, autonomy_default,
tags}] from load_agents() (reflect the live catalog); GET /health -> {status,
llm_available}. Pydantic models, CORS for all origins; add fastapi + uvicorn to
requirements. Add TestClient tests (use_llm=False) for all three endpoints.
```

### Phase 8 — Streamlit frontend ✅
A chat UI talking to the FastAPI backend over HTTP (Streamlit → FastAPI →
`src.handle`), so the UI can be swapped later without touching backend or core.
Chat history in `st.session_state`; sidebar lists `GET /agents`, a `use_llm`
toggle, and a `GET /health` indicator; degrades gracefully if the API is down.

**Shipped as** the [`frontend/`](../agent-recommender/frontend/) package, split into
`app_ui.py` (rendering + session state) and `api_client.py` (the only place that
touches HTTP) — *not* the single `streamlit_app.py` the kickoff prompt below
suggested. The client never imports `src`, so `frontend/tests/test_ui.py` runs by
mocking `requests` — no live server or Streamlit session. Run/usage detail:
[frontend/README.md](../agent-recommender/frontend/README.md).

```
Read PROBLEM_STATEMENT.md, ONBOARDING.md, and PROJECT_HANDOFF.md. Phases 6–7 are
done and the FastAPI backend exposes POST /chat, GET /agents, GET /health. Do
PHASE 8 ONLY: a Streamlit frontend that talks to that backend over HTTP (do not
import src directly — go through the API).
Create agent-recommender/streamlit_app.py: a chat UI with history in
st.session_state; each message POSTs to {API_BASE}/chat with {message, use_llm}
and renders {reply}; API_BASE defaults to http://localhost:8000 (env-overridable).
A sidebar listing GET /agents, a use_llm toggle, and a GET /health indicator.
Handle a down backend gracefully. Add streamlit + requests to requirements.
```

### Person 1 — Data & schema (ongoing)
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Audit the four files in agents/
against AGENT_TEMPLATE.md: confirm identical section headers, valid frontmatter,
and consistent autonomy values. Then fill the Deployment (Hardware/Software)
sections once the manager provides them, keeping the same template. No code
changes.
```

## 6. Working agreements / house rules

1. [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) is the source of truth for
   behavior; this file is for state and ownership.
2. **Never change the [contracts](CONTRACTS.md) without team agreement** — they're
   what lets people work in parallel and stub each other's modules.
3. **Keep the deterministic fallback and the grounding gate intact** — every
   feature must still run with `use_llm=False`, and the bot must never fabricate
   agent facts. This is the project's core safety property.
4. New phases **add modules**; they do not edit the `src/` core or `app.py`.
5. Everyone unit-tests their own module (mock the LLM in CI); Person 5 owns the
   end-to-end tests. Keep `pytest` green.
6. `.env` (the key) and `.chroma/` stay gitignored.
