# Onboarding — Agent Recommender & Q&A Chatbot

> **Audience:** new teammates *and* AI coding agents picking this project up.
> Read this first. It explains what the project is, how it's put together, how to
> run and test it, and how to extend it without breaking the contracts the team
> agreed on.
>
> **Companion docs:** [`PROBLEM_STATEMENT.md`](PROBLEM_STATEMENT.md) is the spec
> (the source of truth for *behavior*). [`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md)
> is the team/state/contracts layer. [`agent-recommender/README.md`](agent-recommender/README.md)
> and [`agent-recommender/INSTALL.md`](agent-recommender/INSTALL.md) cover setup.

---

## 1. TL;DR

A **CLI chatbot over a catalog of AI agents.** Each agent is one Markdown file in
[`agent-recommender/agents/`](agent-recommender/agents/). The bot does two things,
grounded **strictly** in those files (it never invents facts):

1. **Recommend** — you describe a need ("automate UI tests from a live URL") and
   it names the best-fitting agent and explains why.
2. **Info lookup (RAG)** — you ask about an agent ("what are Test Data
   Provisioning's inputs?") and it answers from that agent's doc, or honestly
   says *"I don't have that information"* when the doc says `TBD`.

**Status: backend complete (Phases 1–7), 84 tests passing.** The LLM is
activated and verified live against Gemini (Phase 6), and a FastAPI backend
(Phase 7) exposes the core over HTTP. Phase 8 — a Streamlit UI over the API — is
the only piece left. Runnable today:

```bash
cd agent-recommender
python -m venv .venv && .venv\Scripts\Activate.ps1   # see INSTALL.md for other OSes
pip install -r requirements.txt
python app.py index      # build the vector store from agents/
python app.py            # chat (CLI)
uvicorn api:app --port 8000   # optional: serve the same core over HTTP (docs at /docs)
```

No API key is required to run it — every LLM call has a deterministic, grounded
fallback (set `GEMINI_API_KEY` in `.env` to get LLM-written prose instead).
Intent detection always uses the deterministic router, so each chat turn makes
at most **one** LLM call (the answer/explanation), not two.

---

## 2. Mental model (how a message flows)

```
                         ┌──────────────────────────────────────────────┐
  user message ─────────▶│  chatbot.handle(message)                      │
                         │     1. router.detect_intent(message)          │
                         │            recommend / info / clarify         │
                         └───────┬───────────────┬───────────────┬───────┘
                                 │recommend       │info            │clarify
                                 ▼                ▼                ▼
                    recommender.recommend   info.answer_question   ask one
                                 │                │            clarifying Q
                  search_agents()│   search_sections() (scoped │+ list agents
                                 ▼                ▼   by agent/section)
                        ┌─────────────────────────────────┐
                        │            ChromaDB              │
                        │  agent_summaries  | agent_sections│
                        └─────────────────────────────────┘
                                 ▲
                   index.build_index()  ◀── loader.load_agents(agents/)
```

- **Two collections, two granularities.** `agent_summaries` (one record per
  agent) powers recommendation; `agent_sections` (one record per `##` section)
  powers info lookup with metadata filters (`agent_id`, `section`, autonomy, …).
- **The LLM is optional and swappable.** [`src/llm.py`](agent-recommender/src/llm.py)
  wraps Gemini and returns `None` on any failure; every caller then falls back to
  a deterministic, grounded path. That's why the whole app and test suite run
  offline.
- **Grounding gate.** The info path refuses to answer from empty/`TBD` sections —
  it returns `grounded=False` and an honest message instead of guessing.

---

## 3. Code map

All code lives under [`agent-recommender/`](agent-recommender/).

| File | Role | Phase |
|------|------|-------|
| [`agents/*.md`](agent-recommender/agents/) | The catalog (input data): frontmatter + fixed `##` sections | data |
| [`src/models.py`](agent-recommender/src/models.py) | `Agent` dataclass; `get_section()`, `summary_text()` | 1 |
| [`src/loader.py`](agent-recommender/src/loader.py) | Parse a `.md` → `Agent` (YAML frontmatter + sections) | 1 |
| [`src/index.py`](agent-recommender/src/index.py) | Build the two ChromaDB collections; owns the shared client + embedding fn | 2 |
| [`src/retriever.py`](agent-recommender/src/retriever.py) | `search_agents` / `search_sections` → `list[Hit]` | 2 |
| [`src/recommender.py`](agent-recommender/src/recommender.py) | `recommend(query)`; implied metadata filters; shortlist logic | 3 |
| [`src/llm.py`](agent-recommender/src/llm.py) | Swappable Gemini wrapper, `generate()` / `available()` | 3 |
| [`src/router.py`](agent-recommender/src/router.py) | `detect_intent(query)`; `find_agent(query)` (catalog-driven) | 4 |
| [`src/info.py`](agent-recommender/src/info.py) | `answer_question(query)` RAG + grounding gate | 4 |
| [`src/chatbot.py`](agent-recommender/src/chatbot.py) | `handle(message)` — intent → route → formatted reply | 5 |
| [`app.py`](agent-recommender/app.py) | CLI: `index` subcommand + chat REPL | 5 |
| [`scripts/verify_llm.py`](agent-recommender/scripts/verify_llm.py) | Manual LLM on/off A/B over three queries (hits the real API) | 6 |
| [`api.py`](agent-recommender/api.py) | FastAPI backend: `POST /chat`, `GET /agents`, `GET /health` over `src.handle` | 7 |
| [`src/config.py`](agent-recommender/src/config.py) | Paths, model names, `TOP_K`, thresholds | — |
| [`tests/`](agent-recommender/tests/) | One `test_*.py` per module + `test_chatbot.py` (E2E), `test_llm.py` (mocked LLM guardrails), `test_api.py` (HTTP) | all |

`from src import handle, recommend, answer_question, detect_intent, build_index`
is the public import surface.

---

## 4. The contracts (do not break these)

These signatures are the agreed interfaces (also in `PROJECT_HANDOFF.md` §7).
Everything is wired against them, so changing one ripples across modules and
tests — change only by team agreement.

```python
# Data model
Agent(agent_id, name, domain, tags, autonomy_default,
      autonomy_supported, triggers, sections, source_path)
Agent.get_section(name) -> str | None
Agent.summary_text() -> str

# Retrieval  (Hit = dataclass: agent_id, name, text, score, section, metadata)
search_agents(query, k=3, where=None)   -> list[Hit]
search_sections(query, k=5, where=None) -> list[Hit]

# Paths
recommend(query, *, k=None, use_llm=True, search_fn=None)
    -> {"agents": list[Hit], "explanation": str, "ambiguous": bool}
detect_intent(query, *, use_llm=False)   # deterministic router by default
    -> "recommend" | "info" | "clarify"
answer_question(query, *, k=None, use_llm=True, search_fn=None)
    -> {"answer": str, "sources": list[Hit], "grounded": bool}

# Orchestration
handle(message, *, use_llm=True) -> str
```

**Two conventions worth internalizing:**
- **`use_llm=False`** anywhere forces the deterministic path → use it in tests.
- **`search_fn=`** lets you inject a stub retriever so a path can be unit-tested
  without a live Chroma store (see the existing tests for the pattern).

---

## 5. Running and testing

```bash
cd agent-recommender
pytest                 # 84 passed — runs against the real agents/ catalog
python app.py index    # (re)build .chroma/ from agents/  (gitignored)
python app.py          # REPL: describe a task, or ask about an agent; 'exit' to quit
uvicorn api:app --port 8000   # optional: HTTP API (POST /chat, GET /agents, GET /health)
python scripts/verify_llm.py  # optional: LLM on/off A/B (needs a key + a built store)
```

- **First run is slow (~1 min)**: ChromaDB downloads its default embedding model
  (all-MiniLM-L6-v2, runs locally via onnxruntime). Subsequent runs are fast.
- Tests build a **throwaway** store in a temp dir and restore `config.CHROMA_PATH`
  afterward, so they don't touch your real `.chroma/`.
- The acceptance criteria (`PROBLEM_STATEMENT.md` §9) are all covered by
  [`tests/test_chatbot.py`](agent-recommender/tests/test_chatbot.py): correct
  recommendation, grounded answer, honest "not available", vague→clarify, and
  new-agent discoverability after re-indexing.

---

## 6. Extending the project

The architecture was built to grow. Common changes and where to make them:

| You want to… | Do this | No changes needed in |
|---|---|---|
| **Add an agent** | Drop a new `.md` in `agents/` (follow the template in `PROBLEM_STATEMENT.md` §3), then `python app.py index` | any `.py` — nothing is hard-coded to 4 agents |
| **Fill the `TBD` Deployment fields** | Edit the agent `.md` files, re-index. The grounding gate auto-flips those answers to grounded once real content exists | code |
| **Swap the embedding model** | Change `index.get_embedding_function()` (one function) and re-index | retriever, paths |
| **Swap the LLM** | Reimplement `src/llm.py`'s `generate()`/`available()`; keep the signatures | every caller (they only use `generate`) |
| **Tune recommendation behavior** | `config.py`: `RECOMMEND_TOP_K`, `NO_MATCH_SCORE`, `AMBIGUITY_DELTA` | logic |
| **Use / extend the web API** | The FastAPI backend already exists in `api.py` (Phase 7), importing `handle` from `src`; add endpoints there. A Streamlit UI over it is Phase 8 | `src/` core |
| **Recognize new intents/sections** | Extend the regexes in `router.py` / `info.py` (`_SECTION_PATTERNS`); keep the rule-based fallback deterministic | contracts |

**House rules for any contributor (human or AI):**
1. Read `PROBLEM_STATEMENT.md` (behavior) and `PROJECT_HANDOFF.md` (state) first.
2. Don't change the §4 contract signatures without team agreement.
3. Keep the deterministic fallback working — features must run with `use_llm=False`.
4. Add/extend tests for what you change; keep `pytest` green.
5. Never fabricate agent facts — preserve the grounding gate.

---

## 7. Gotchas & environment notes

- **Python 3.14 + corporate network:** dependency *resolution* works (wheels
  exist for cp314), but installing from public PyPI can hit `ReadTimeoutError`
  behind a proxy. If `pip install` times out, raise the timeout
  (`pip install -r requirements.txt --timeout 120 --retries 10`) or use your
  org's internal package mirror (`--index-url …`). This is environmental, not a
  project bug.
- **The em-dash (`—`) in CLI output** may render as `?`/`�` in a Windows console
  using a non-UTF-8 codepage — a display artifact only; the data is correct.
- **`.chroma/` and `.env`** are gitignored. The store is rebuilt by `app.py index`;
  the key file is per-developer.
- **No key set?** That's fine — explanations/answers come from the grounded
  fallbacks (verbatim section text, template explanations). Set `GEMINI_API_KEY`
  for LLM-written prose.
- **Free-tier rate limits (HTTP 429):** Gemini's free tier caps requests per
  minute/day. When exhausted, `llm.generate()` returns `None` and the path falls
  back to its deterministic answer — so a "live" reply can silently look like the
  offline one. It's not a bug; wait for the window to reset or use a higher-limit
  key. Each chat turn makes at most one LLM call (intent is deterministic).

---

## 8. Where to look when…

- *"Why did it recommend X?"* → `recommender.py` (ranking + thresholds) and the
  `agent_summaries` records built in `index.py`.
- *"Why did it say it doesn't know?"* → `info.py` `_looks_missing()` /
  `_build_where()` and the section's content in the agent `.md`.
- *"Why was this classified as info vs recommend?"* → `router.py` regexes and
  `find_agent()`.
- *"How is a reply formatted?"* → `chatbot.py` `_format_recommendation` /
  `_format_info` / `_clarify_reply`.
