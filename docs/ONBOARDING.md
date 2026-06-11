# Onboarding — Agent Recommender & Q&A Chatbot

> **Audience:** new teammates and AI coding agents picking this project up. This
> is the **orientation map** — what to read in what order, where each piece of
> code lives, and where to look when you're debugging. It deliberately does *not*
> repeat the spec, the architecture, or the run steps; it points you to them.

---

## 1. Read these in this order

1. [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) — *what* the system must do (the
   spec). Start here.
2. [ARCHITECTURE.md](ARCHITECTURE.md) — how it's structured and *why* (two
   collections, RAG vs. semantic search, LLM-optional, the layers).
3. [DATA_FLOW.md](DATA_FLOW.md) — how one message travels end to end.
4. [CONTRACTS.md](CONTRACTS.md) — the interface signatures every module agrees on.
   **Internalize these — do not change them without team agreement.**
5. [INSTALL.md](INSTALL.md) → get it running. Then poke it via the CLI.
6. [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) — current status, the phase log, and
   who owns what.

The 30-second version: it's a **chatbot over a catalog of AI agents** — reachable
from a CLI, an HTTP API, and a Streamlit web UI — each defined by one Markdown
file. It **recommends** an agent for a
described need, or **answers questions** about an agent grounded strictly in its
doc — and says *"I don't have that information"* rather than inventing facts. No
API key is needed to run it (every LLM call has a deterministic, grounded
fallback).

## 2. Code map

All code lives under [`agent-recommender/`](../agent-recommender/). One module per
responsibility; the public import surface is
`from src import handle, recommend, answer_question, detect_intent, build_index`.

| File | Role | Phase |
|------|------|-------|
| [`agents/*.md`](../agent-recommender/agents/) | The catalog (input data): frontmatter + fixed `##` sections | data |
| [`src/models.py`](../agent-recommender/src/models.py) | `Agent` dataclass; `get_section()`, `summary_text()` | 1 |
| [`src/loader.py`](../agent-recommender/src/loader.py) | Parse a `.md` → `Agent` (YAML frontmatter + sections) | 1 |
| [`src/index.py`](../agent-recommender/src/index.py) | Build the two ChromaDB collections from the catalog (`build_index`) | 2 |
| [`src/store.py`](../agent-recommender/src/store.py) | Shared cached Chroma client + embedding fn + collection handles; `refresh_catalog_caches()` | 2 |
| [`src/retriever.py`](../agent-recommender/src/retriever.py) | `search_agents` / `search_sections` → `list[Hit]` | 2 |
| [`src/recommender.py`](../agent-recommender/src/recommender.py) | `recommend(query)`; implied filters; shortlist logic | 3 |
| [`src/llm.py`](../agent-recommender/src/llm.py) | Swappable Gemini wrapper, `generate()` / `available()` | 3 |
| [`src/router.py`](../agent-recommender/src/router.py) | `detect_intent(query)`; `find_agent(query)` (catalog-driven) | 4 |
| [`src/info.py`](../agent-recommender/src/info.py) | `answer_question(query)` RAG + grounding gate | 4 |
| [`src/chatbot.py`](../agent-recommender/src/chatbot.py) | `handle(message)` — intent → route → formatted reply | 5 |
| [`app.py`](../agent-recommender/app.py) | CLI: `index` subcommand + chat REPL | 5 |
| [`scripts/verify_llm.py`](../agent-recommender/scripts/verify_llm.py) | Manual LLM on/off A/B over three queries (hits the real API) | 6 |
| [`scripts/watch_agents.py`](../agent-recommender/scripts/watch_agents.py) | watchdog watcher: auto re-index + cache refresh on `agents/` changes | — |
| [`api.py`](../agent-recommender/api.py) | FastAPI backend over `src.handle` | 7 |
| [`frontend/`](../agent-recommender/frontend/) | Streamlit web UI (`app_ui.py`) + HTTP client (`api_client.py`); talks to `api.py` only, never `src` | 8 |
| [`src/config.py`](../agent-recommender/src/config.py) | Paths, model names, `TOP_K`, thresholds | — |
| [`tests/`](../agent-recommender/tests/) + [`frontend/tests/`](../agent-recommender/frontend/tests/) | One `test_*.py` per module + E2E + mocked-LLM + API + store-caching tests; `frontend/tests/test_ui.py` mocks the HTTP layer | all |

## 3. Where to look when…

- *"Why did it recommend X?"* → `recommender.py` (ranking + thresholds) and the
  `agent_summaries` records built in `index.py`. Thresholds: [CONFIGURATION.md](CONFIGURATION.md).
- *"Why did it say it doesn't know?"* → `info.py` `_looks_missing()` /
  `_build_where()`, and the section's content in the agent `.md`. The mechanism:
  [DATA_FLOW.md](DATA_FLOW.md#the-grounding-gate).
- *"Why was this classified as info vs. recommend?"* → `router.py` regexes and
  `find_agent()`. The rules: [DATA_FLOW.md](DATA_FLOW.md#step-2--intent-detection-deterministic-no-llm).
- *"How is a reply formatted?"* → `chatbot.py` `_format_recommendation` /
  `_format_info` / `_clarify_reply`.
- *"What's the exact signature of …?"* → [CONTRACTS.md](CONTRACTS.md).

## 4. Common changes → which doc tells you how

The architecture was built to grow. Each task has a single doc that owns the
"how"; this table is just the index into them.

| You want to… | Go to |
|---|---|
| Add a new agent | [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) (then `python app.py index`) |
| Fill the `TBD` Deployment fields | [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) — the grounding gate auto-flips those answers once real content exists |
| Swap the embedding model | [CONFIGURATION.md](CONFIGURATION.md) + [ARCHITECTURE.md](ARCHITECTURE.md) (`store.get_embedding_function()`) |
| Swap the LLM | [ARCHITECTURE.md](ARCHITECTURE.md#5-the-llm-optional-pattern) (reimplement `src/llm.py`, keep the signatures) |
| Tune recommendation behavior | [CONFIGURATION.md](CONFIGURATION.md) (`RECOMMEND_TOP_K`, `NO_MATCH_SCORE`, `AMBIGUITY_DELTA`) |
| Use / extend the web API | [API_REFERENCE.md](API_REFERENCE.md) (`api.py` imports `handle` from `src`) |
| Work on the Streamlit web UI | [frontend/README.md](../agent-recommender/frontend/README.md) (`frontend/app_ui.py` + `api_client.py`, HTTP-only) |
| Write or run tests | [TESTING.md](TESTING.md) |
| Run a demo / troubleshoot | [RUNBOOK.md](RUNBOOK.md) |

**House rules** for any contributor live in
[PROJECT_HANDOFF.md](PROJECT_HANDOFF.md#6-working-agreements--house-rules) — read
them before you change code. The short version: don't change the contracts, keep
the deterministic fallback and grounding gate intact, add tests, keep `pytest`
green.
