# Project Handoff v2 — Agent Recommender & Q&A Chatbot
## LLM Activation → CLI Verification → Web Demo (FastAPI + Streamlit)

> **Audience:** teammates *and* Claude Code sessions picking up the next block of
> work. Read this top to bottom before touching anything.
>
> **Companion docs (already in the repo):**
> - `PROBLEM_STATEMENT.md` — the behavior spec (source of truth for *what* it does).
> - `ONBOARDING.md` — orientation, mental model, code map, contracts, gotchas.
> - This file **supersedes the previous build-phase handoff** and defines the new
>   work (Phases 6–8). It does not change any agreed contract.

---

## 1. Why this handoff exists

The core product is **done**: Phases 1–5 are complete and the suite now has
**84 tests passing**. It runs today as a CLI chatbot over the agent catalog,
with two paths (recommend / info) grounded strictly in the agent `.md` files.

> **Progress update:** Phases **6 (LLM activate + verify)** and **7 (FastAPI
> backend)** described below are now **complete and tested**. Only **Phase 8
> (Streamlit frontend)** remains.

What was left is **not new core logic** — it's three things:

1. **Activate and verify the LLM for ourselves.** The Gemini wrapper already
   exists; the whole app already calls it. We've now added a `GEMINI_API_KEY`, so
   the live path can finally run. But the test suite runs with `use_llm=False`,
   which means the *live* Gemini path is the least-exercised part of the system.
   We need to switch it on, watch it behave, and lock in a few guardrail tests.
2. **FastAPI backend** — a thin HTTP layer over the existing core.
3. **Streamlit frontend** — a simple chat UI for the user demo.

> **Important correction to a common assumption:** there is *no LLM layer to build
> from scratch.* Per `ONBOARDING.md` §3, `src/llm.py` already exists as a
> swappable Gemini wrapper (`generate()` / `available()`), built in Phase 3, and
> every path already calls it with a `use_llm` flag and a deterministic fallback.
> "LLM integration" at this point = **activate + verify**, not author.

---

## 2. Current state (verified against the repo docs)

| Area | State |
|------|-------|
| Phases 1–5 (model, loader, indexer, retriever, recommender, router, info, chatbot, CLI) | ✅ Complete |
| Test suite | ✅ 84 passing (deterministic/mocked; CI needs no key) |
| CLI | ✅ Runnable: `python app.py index` then `python app.py` |
| `src/llm.py` Gemini wrapper (`generate()`/`available()`) | ✅ Exists; returns `None` on any failure → callers fall back |
| `GEMINI_API_KEY` | ✅ In `.env` (gitignored) |
| **Live LLM path exercised end-to-end** | ✅ **Done (Phase 6)** — verified live via `scripts/verify_llm.py`; mocked guardrail tests in `tests/test_llm.py` |
| Intent detection | ✅ Deterministic by default — `handle()` makes ≤1 LLM call per turn |
| FastAPI backend | ✅ **Done (Phase 7)** — `api.py`: `POST /chat`, `GET /agents`, `GET /health`; tests in `tests/test_api.py` |
| Streamlit frontend | ⬜ Not started (Phase 8) |
| Deployment (hardware/software) doc fields | ⬜ Still `TBD` — info path correctly answers "not available" until filled |

---

## 3. How it runs today (baseline — don't regress this)

```bash
cd agent-recommender
python -m venv .venv && .venv\Scripts\Activate.ps1   # see INSTALL.md for macOS/Linux
pip install -r requirements.txt
python app.py index      # build .chroma/ from agents/   (first run ~1 min: downloads embedding model)
python app.py            # chat REPL; 'exit' to quit
uvicorn api:app --port 8000   # optional: HTTP backend (Phase 7)
pytest                   # 84 passed
```

- **No key needed** to run — grounded deterministic fallbacks cover every LLM
  call. Setting `GEMINI_API_KEY` in `.env` switches on LLM-written prose.
- Public import surface: `from src import handle, recommend, answer_question, detect_intent, build_index`.

---

## 4. Message flow (recap — full version in `ONBOARDING.md` §2)

```
user message → chatbot.handle(message)
                 → router.detect_intent()  → recommend | info | clarify
                       recommend → recommender.recommend() → search_agents()  ─┐
                       info      → info.answer_question()  → search_sections() ─┤→ ChromaDB
                       clarify   → ask one question + list agents               │  (2 collections)
                 every LLM call → src/llm.py.generate(); None → deterministic fallback
```

Two collections, two granularities: `agent_summaries` (recommendation) and
`agent_sections` (info lookup, filtered by `agent_id`/`section`/metadata).

---

## 5. Contracts — DO NOT BREAK (from `ONBOARDING.md` §4 / `PROBLEM_STATEMENT.md` §7)

Everything is wired against these. Phases 6–8 must **consume** them, not change
them. Change a signature only by team agreement.

```python
# Data model
Agent(agent_id, name, domain, tags, autonomy_default,
      autonomy_supported, triggers, sections, source_path)
Agent.get_section(name) -> str | None
Agent.summary_text() -> str

# Retrieval  (Hit = dataclass: agent_id, name, text, score, section, metadata)
search_agents(query, k=3, where=None)   -> list[Hit]
search_sections(query, k=5, where=None) -> list[Hit]

# LLM wrapper
llm.available() -> bool          # True when the key is present and the client is usable
llm.generate(prompt) -> str | None   # None on ANY failure → caller falls back

# Paths
recommend(query, *, k=None, use_llm=True, search_fn=None)
    -> {"agents": list[Hit], "explanation": str, "ambiguous": bool}
detect_intent(query, *, use_llm=False) -> "recommend" | "info" | "clarify"  # deterministic router by default
answer_question(query, *, k=None, use_llm=True, search_fn=None)
    -> {"answer": str, "sources": list[Hit], "grounded": bool}

# Orchestration
handle(message, *, use_llm=True) -> str
```

**Two conventions to keep using:**
- `use_llm=False` forces the deterministic path → use it in fast/CI tests.
- `search_fn=` injects a stub retriever → unit-test a path without a live store.

---

## 6. New work — order and rationale

```
Phase 6  Activate + verify the LLM   ✅ DONE  (verify_llm.py + mocked guardrail tests)
            │   live path works AND stays grounded
            ▼
Phase 7  FastAPI backend             ✅ DONE  (api.py; no core changes)
            │
            ▼
Phase 8  Streamlit frontend          ⬜ TODO  (chat UI calling the FastAPI backend)
            ▼
         Demo-ready (see §10 runbook)
```

Do them in order: you want the LLM behaving correctly *before* you expose it over
HTTP, and a working API *before* you build a UI against it.

---

## 7. Phase 6 — LLM activation & verification ("see it for ourselves") ✅ DONE

> **Completed.** `scripts/verify_llm.py` (live on/off A/B) and `tests/test_llm.py`
> (10 mocked guardrail tests, no key needed) are in place. Verified live against
> Gemini: facts and grounding match across LLM-on vs LLM-off, and the `TBD` query
> stays honest with the LLM on. As a follow-on, `detect_intent` now defaults to
> the deterministic router, so `handle()` makes ≤1 LLM call per turn. The brief
> below is kept as the original scope.

**Why this matters.** The 68 existing tests deliberately bypass the LLM
(`use_llm=False`). So the live Gemini path has effectively never been exercised by
the suite. The risk isn't that it errors — the wrapper already fails safe to the
fallback — it's that the **LLM could phrase an answer that drifts from the
grounded facts** (e.g. soften the honest "I don't have that" on a `TBD` field).
Phase 6 confirms the live path works *and* that the grounding gate still holds
when the LLM is on.

**Tasks**
1. **Env/availability check.** Confirm `.env` loads and `llm.available()` returns
   `True` with the key set, `False` without. (If it's `False` with a key present,
   the `.env` isn't being read — fix loading, not the wrapper.)
2. **Generate smoke check.** `llm.generate("Say OK")` returns non-empty text;
   simulate a failure (bad key/no network) and confirm it returns `None` without
   raising — the contract the whole app depends on.
3. **CLI A/B observation.** Run the same set of queries twice — once with the LLM
   on, once with it off — and eyeball them side by side:
   - a recommendation query (e.g. "automate UI tests from a live URL")
   - an info query with real content (e.g. "inputs to Test Data Provisioning")
   - a `TBD` query (e.g. "what hardware does the User Story Analyser need?")
   The **facts and the grounding verdict must be identical** in both runs; only the
   *prose* should get richer with the LLM on. The `TBD` query must still say it
   doesn't have that info.
4. **Guardrail tests (mocked — no key, no quota in CI).** Add tests that
   monkeypatch `llm.generate`:
   - when `generate` returns a canned string → the path uses it (LLM path taken);
   - when `generate` returns `None` → the path falls back deterministically;
   - **grounding holds under the LLM:** if retrieved sections are empty/`TBD`,
     `answer_question(...)["grounded"]` is `False` *regardless* of what the mocked
     LLM returns. This is the most important new test.
5. **Manual verify script.** Add `scripts/verify_llm.py` that hits the real API
   once and prints the A/B (LLM on vs off) for the three queries above — this is
   the "see it for ourselves" artifact for the team/manager.

**Constraints**
- Do **not** change any contract signature or the deterministic fallbacks.
- Keep the existing 68 tests green; new mocked tests must pass **without** a key.

**Acceptance criteria**
- `llm.available()` is `True` with a key, `False` without; `generate()` never
  raises (returns `None` on failure).
- The CLI A/B run shows richer prose but identical facts and identical grounding
  behavior, including the honest "not available" on `TBD`.
- New mocked guardrail tests pass in CI without a key; total test count goes up
  and the suite stays green.
- `scripts/verify_llm.py` prints a clear LLM-on vs LLM-off comparison.

**Claude Code prompt — Phase 6**
```
Read PROBLEM_STATEMENT.md, ONBOARDING.md, and this PROJECT_HANDOFF_v2.md. The core
(Phases 1–5) is complete and src/llm.py already wraps Gemini (generate()/available()).
Do PHASE 6 ONLY: activate and verify the live LLM path. Do NOT change any contract
signature, the deterministic fallbacks, or the existing tests' behavior.

1. Confirm .env loading and that llm.available() is True with GEMINI_API_KEY set,
   False without. Confirm llm.generate() returns text on success and None (no
   exception) on failure.
2. Add scripts/verify_llm.py: for three queries (a recommend query, an info query
   with real content, and a TBD/deployment query), call handle(..., use_llm=True)
   and handle(..., use_llm=False) and print them side by side so we can eyeball
   that facts + grounding match and only prose differs.
3. Add MOCKED guardrail tests (monkeypatch llm.generate, so CI needs no key):
   (a) when generate returns a canned string, the LLM output is used;
   (b) when generate returns None, the path falls back deterministically;
   (c) CRITICAL: when retrieved sections are empty/TBD, answer_question()["grounded"]
       is False regardless of what the mocked LLM returns.
Keep all 68 existing tests green. Run pytest and show results, then run
scripts/verify_llm.py and show its output.
```

---

## 8. Phase 7 — FastAPI backend ✅ DONE

> **Completed.** `api.py` exposes `POST /chat`, `GET /agents`, and `GET /health`
> over the unchanged `src` core, with CORS open to all origins; `tests/test_api.py`
> covers all three endpoints (and CORS) with `use_llm=False`. `fastapi` +
> `uvicorn[standard]` (and `httpx` for the test client) are in `requirements.txt`.
> Run with `uvicorn api:app --reload --port 8000` (docs at `/docs`). The brief
> below is kept as the original scope.

**Goal.** Expose the existing core over HTTP with **zero changes to `src/`**.
`ONBOARDING.md` §6 already prescribes this: "Add a web/API front end → new module
that imports `handle` from `src` — the core is interface-decoupled by design."

**Tasks**
- New module `agent-recommender/api.py` importing from the public surface
  (`handle`, plus `loader.load_agents` and `llm.available` for the extra
  endpoints).
- Endpoints (Pydantic request/response models):
  - `POST /chat` — body `{ "message": str, "use_llm": bool = true }` →
    `{ "reply": str }` (just returns `handle(message, use_llm=use_llm)`).
  - `GET /agents` → list of `{ agent_id, name, domain, autonomy_default, tags }`
    loaded from the catalog (never hard-code the count — it must reflect whatever
    is in `agents/`).
  - `GET /health` → `{ "status": "ok", "llm_available": llm.available() }`.
- Enable **CORS** (so the Streamlit/browser frontend can call it).
- Add `fastapi` and `uvicorn[standard]` to `requirements.txt`.
- Run with `uvicorn api:app --reload --port 8000`.

**Constraints**
- Do not modify anything under `src/`. Do not break the CLI (`app.py`).
- API tests should use `use_llm=False` to stay deterministic and fast.

**Acceptance criteria**
- `POST /chat` returns the same reply `handle()` produces for a known query.
- `GET /agents` lists every agent currently in `agents/` (add a 5th `.md`,
  re-index, and it appears — no code change).
- `GET /health` reports `llm_available` correctly with/without a key.
- CLI still works; `src/` unchanged; `pytest` stays green (incl. new API tests).

**Claude Code prompt — Phase 7**
```
Read PROBLEM_STATEMENT.md, ONBOARDING.md, and PROJECT_HANDOFF_v2.md. Phase 6 is done.
Do PHASE 7 ONLY: a FastAPI backend that wraps the existing core. Do NOT modify
anything under src/ and do NOT break the CLI.

Create agent-recommender/api.py using FastAPI:
- POST /chat: body {message: str, use_llm: bool = true} -> {reply: str}, returns
  handle(message, use_llm=use_llm) (imported from src).
- GET /agents: -> list of {agent_id, name, domain, autonomy_default, tags} built
  from loader.load_agents() — reflect the live catalog, never hard-code 4.
- GET /health: -> {status: "ok", llm_available: <llm.available()>}.
Use Pydantic models, enable CORS for all origins, and add fastapi and
uvicorn[standard] to requirements.txt.
Add tests using FastAPI's TestClient (use_llm=False) for all three endpoints.
Run pytest and show results, and print the exact uvicorn command to start it.
```

---

## 9. Phase 8 — Streamlit frontend

**Goal.** A simple chat UI for the user demo that talks to the FastAPI backend.
Keep the layers separate (Streamlit → FastAPI → `src.handle`) so the UI can be
swapped for React later without touching backend or core.

**Tasks**
- New file `agent-recommender/streamlit_app.py`.
- Chat UI: input box + message history kept in `st.session_state`; each user
  message is POSTed to `<API_BASE>/chat` and the reply rendered. `API_BASE`
  defaults to `http://localhost:8000`, overridable via env var.
- Sidebar: list agents from `GET /agents`; a `use_llm` toggle passed through to
  `/chat`; a small health indicator from `GET /health`.
- Graceful error if the backend is unreachable (don't crash — show a message to
  start the API).
- Add `streamlit` and `requests` to `requirements.txt`.
- Run with `streamlit run streamlit_app.py` (FastAPI must be running too).

**Acceptance criteria**
- With FastAPI up, typing a query shows the bot's reply in the chat window.
- The sidebar lists the live catalog and the health indicator reflects key status.
- Toggling `use_llm` visibly changes the prose richness.
- This is sufficient as the backend + frontend demo.

**Claude Code prompt — Phase 8**
```
Read PROBLEM_STATEMENT.md, ONBOARDING.md, and PROJECT_HANDOFF_v2.md. Phases 6–7 are
done and the FastAPI backend exposes POST /chat, GET /agents, GET /health. Do
PHASE 8 ONLY: a Streamlit frontend that talks to that backend over HTTP (do not
import src directly — go through the API).

Create agent-recommender/streamlit_app.py:
- A chat UI with message history in st.session_state; each message POSTs to
  {API_BASE}/chat with {message, use_llm} and renders {reply}. API_BASE defaults
  to http://localhost:8000 and is overridable via an env var.
- A sidebar that lists agents from GET /agents, has a use_llm toggle, and shows a
  health indicator from GET /health.
- Handle a down backend gracefully (show "start the API first", don't crash).
Add streamlit and requests to requirements.txt. Print the two commands needed to
run the full demo (uvicorn + streamlit).
```

---

## 10. Demo runbook (full stack)

Two terminals, from `agent-recommender/` with the venv active:

```bash
# Terminal 1 — backend
python app.py index            # only if .chroma/ isn't built yet
uvicorn api:app --port 8000

# Terminal 2 — frontend
streamlit run streamlit_app.py
```

What to show the audience:
1. A **recommendation** ("I need to automate UI tests from a live URL") → it names
   `test-script-generator` and explains why.
2. An **info** question ("What are Test Data Provisioning's inputs?") → grounded
   answer from the doc.
3. A **missing-data** question ("What hardware does the User Story Analyser
   need?") → honest "I don't have that information" (proves it doesn't fabricate).
4. The **`use_llm` toggle** → same facts, richer wording, to show the LLM layer is
   live but still grounded.

---

## 11. Updated repo layout (new files only)

```
agent-recommender/
├── api.py                  # ✅ (Phase 7) FastAPI backend over src.handle
├── streamlit_app.py        # ⬜ (Phase 8) chat UI calling the API — TODO
├── scripts/
│   └── verify_llm.py       # ✅ (Phase 6) LLM on/off A/B printout
├── app.py                  # unchanged CLI
├── src/                    # unchanged core
├── agents/                 # unchanged catalog
└── tests/                  # + test_llm.py (Phase 6, mocked) + test_api.py (Phase 7)
```

---

## 12. House rules (human or AI contributor)

1. Read `PROBLEM_STATEMENT.md` (behavior) and this handoff (state) first.
2. **Never change the §5 contracts** without team agreement.
3. **Keep the deterministic fallback and the grounding gate intact** — every
   feature must still run with `use_llm=False`, and the bot must never fabricate
   agent facts. This is the project's core safety property.
4. New phases add modules; they do **not** edit `src/` core or `app.py`.
5. Keep `pytest` green; add tests for what you add (mock the LLM in CI).
6. `.env` (the key) and `.chroma/` stay gitignored.

---

## 13. Gotchas relevant to the new work

- **`.env` not loading:** if `llm.available()` is `False` with a key set, the env
  loader isn't running before the client initializes — check import order, not the
  wrapper.
- **CORS:** without it, the browser/Streamlit calls to FastAPI fail silently from
  the UI side. Enable it in `api.py`.
- **Backend must be up first:** Streamlit depends on the API; the runbook order
  matters. The UI should degrade gracefully, not crash, if the API is down.
- **Quota/cost:** only `scripts/verify_llm.py` and live CLI runs hit the real API;
  CI uses mocked `generate`, so it neither needs a key nor spends quota.
- **Windows console:** em-dashes in CLI output may render as `?`/`�` on a non-UTF-8
  codepage — display only; the data is correct (per `ONBOARDING.md` §7).
- **Corporate proxy + pip:** if installing `fastapi`/`streamlit` times out, raise
  the timeout/retries or use your org mirror — environmental, not a project bug.
