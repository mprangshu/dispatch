# Architecture

How the Agent Recommender & Q&A Chatbot is put together, and *why* it's shaped
this way. Read [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) first for the
behavior spec; this doc explains the structure that delivers it.

---

## 1. The one-paragraph mental model

The catalog of agents is just a folder of Markdown files (`agents/*.md`). An
**indexer** reads those files once and writes them into a local vector database
(**ChromaDB**) in two granularities. At chat time, a message is **classified**
into an intent, **routed** to one of two retrieval paths (recommend or info),
the relevant text is pulled from ChromaDB, and an **LLM** turns that text into a
grounded reply — or, if the LLM isn't available, a deterministic fallback does.
Everything important runs offline; the LLM only makes the prose nicer.

```
agents/*.md ──(index.py)──► ChromaDB ──(retriever.py)──► recommend / info paths
                              ▲                                   │
                              │                                   ▼
                          (offline,                          chatbot.handle
                         re-runnable)        intent router ──►  │   │
                                                                ▼   ▼
                                                       app.py (CLI)  api.py (HTTP)
                                                                       │
                                                              frontend/ (Streamlit UI)
```

## 2. Layer separation: `src → api → UI`

The codebase is deliberately layered so the interface can change without
touching the brains. Each layer only depends on the one below it.

| Layer | Files | Responsibility | Knows about |
|-------|-------|----------------|-------------|
| **Core** | `src/` | All business logic: load, index, retrieve, route, recommend, answer, orchestrate. | Nothing above it. No HTTP, no terminal. |
| **CLI** | `app.py` | A REPL shell over the core. | `src` only. |
| **API** | `api.py` | A thin HTTP layer over the core (FastAPI). Adds *no* business logic. | `src` only. |
| **UI** | `frontend/` (`app_ui.py` + `api_client.py`) | A Streamlit browser chat front end that calls the API. | `api` (over HTTP) — never imports `src`. |

The rule the code enforces: **`api.py` imports the public surface of `src` and
adds nothing.** `POST /chat` is literally `handle(message, use_llm=...)`. That's
why the CLI and the API give identical answers — they share one core. (A test
asserts this: `reply == handle(message, use_llm=False)`.)

The public surface is exported from `src/__init__.py`:
`handle`, `recommend`, `answer_question`, `detect_intent`, `build_index`. See
[CONTRACTS.md](CONTRACTS.md) for the signatures.

## 3. The two-collection ChromaDB design

ChromaDB is the *only* datastore. It holds **both** the embeddings (for semantic
search) **and** the metadata (for exact filters like `autonomy_default = L4`), so
there's no separate relational database.

The indexer writes each agent into **two collections at different granularities**:

| Collection | One record per… | Document that gets embedded | Used by |
|------------|-----------------|------------------------------|---------|
| `agent_summaries` (coarse) | **agent** | `name` + Overview + tags (`Agent.summary_text()`) | the **recommendation** path |
| `agent_sections` (fine) | **`## section`** | `"<name> — <section>\n\n<body>"` | the **info / RAG** path |

Why two? The two questions need different chunk sizes:

- *"Which agent should I use?"* is a **whole-agent** comparison → match against one
  compact summary per agent. Coarse is better; you don't want five sections of the
  same agent crowding the results.
- *"What are the inputs to Test Data Provisioning?"* needs **one specific section**
  → match against per-section chunks, scoped by metadata to the right agent and
  section. Fine is better.

Each section record stores `agent_id`, `name`, `section`, and the flattened
frontmatter as metadata, so retrieval can be filtered precisely. List fields
(`tags`, `autonomy_supported`, `triggers`) are flattened to comma-joined strings
because Chroma metadata values must be scalars (`str/int/float/bool`).

The store is **rebuilt cleanly on every index run** (both collections are dropped
and recreated). That's what makes "add a `.md` file, re-index, done — no code
changes" work.

## 4. RAG vs. semantic-search split

Both paths retrieve from ChromaDB, but they use the result differently:

- **Recommendation path** (`recommender.py`) = *semantic search + ranking*. It
  searches `agent_summaries`, ranks by similarity, and decides: one clear winner,
  an ambiguous shortlist, or no match. The LLM only writes the "why it fits"
  explanation — the *choice* is made by the scores and thresholds.

- **Info path** (`info.py`) = *Retrieval-Augmented Generation*. It retrieves the
  right section chunk(s), then hands that text to the LLM with a strict
  instruction: **answer only from this text**. The LLM generates prose, but the
  facts come entirely from the retrieved document.

An **intent router** (`router.py`) sits in front and decides which path a message
goes to (`recommend` / `info` / `clarify`). `chatbot.py` orchestrates: route →
call path → format one reply.

## 5. The LLM-optional pattern

The LLM (Google Gemini by default) is a **swappable, optional** component, isolated
behind one wrapper: `src/llm.py`.

- `llm.generate(prompt, system=...)` returns a string **or `None`**. It returns
  `None` whenever the LLM can't be used — no `GEMINI_API_KEY`, SDK missing,
  network error, or quota exhausted (HTTP 429). **It never raises.**
- Every caller treats `None` as "fall back to the deterministic, grounded path."
  - `recommender` → a templated explanation built from the retrieved overview.
  - `info` → quotes the retrieved section verbatim.
- Result: the whole chatbot **runs fully offline**, and the test suite needs no
  API key. With a key set, the same facts come back wrapped in nicer prose.

This is also why the embeddings are chosen to need **no API key**: ChromaDB's
default model (`all-MiniLM-L6-v2`) runs locally via `onnxruntime`. Swappable in
exactly one function, `store.get_embedding_function()` (re-exported by `index`).

A second deliberate choice: **intent detection does not use the LLM in normal
operation.** `chatbot.handle` always classifies with the deterministic rule-based
router and threads `use_llm` only into the *answer/explanation* generation. This
halves LLM calls per message and keeps routing fast and predictable. (`router.py`
*can* use an LLM pass via `detect_intent(..., use_llm=True)`, but `handle` doesn't
turn it on.)

## 6. The grounding gate (the safety property)

The system must **never fabricate** agent facts. This is enforced structurally,
not just by prompting:

1. Before the LLM is even consulted, `info.py` checks whether the section it would
   answer from has *real content*. If it's `TBD` / "not specified" / empty
   (`_looks_missing`), it returns `grounded=False` with an honest "I don't have
   that information" — **the LLM is never called**, so it can't invent specs.
2. If the LLM *is* called and decides the context lacks the answer, it returns the
   sentinel `INSUFFICIENT_CONTEXT`, which the code maps to `grounded=False`.

A dedicated test feeds the LLM a fabricated hardware spec for a `TBD` field and
asserts none of it leaks into the reply. See [DATA_FLOW.md](DATA_FLOW.md#the-grounding-gate)
and [TESTING.md](TESTING.md).

## 7. Configurability summary

Everything tunable lives in `src/config.py` (paths, collection names, model name,
`TOP_K`, and the recommendation thresholds). The embedding model, the LLM model,
and the retrieval thresholds can each be changed in one place without touching the
rest of the architecture. See [CONFIGURATION.md](CONFIGURATION.md).

## 8. Shared store, caching & cache invalidation

Both the indexer and the retriever go through one module — **`src/store.py`** —
which owns process-level singletons: a cached `PersistentClient`, the embedding
function (built once), and handles to the two collections. Opening the client and
re-instantiating the onnx embedding wrapper are expensive, so caching them keeps
every query fast and avoids Chroma "multiple client" warnings. `index.py` and
`retriever.py` import these accessors (index re-exports them for API
compatibility); neither opens its own client. The client re-opens only if a
*different* path is requested (e.g. tests pointing `CHROMA_PATH` at a temp dir).

Because some state is **derived from the catalog**, a re-index must invalidate it.
`store.refresh_catalog_caches()` — called at the end of `build_index()` — drops the
cached collection handles and clears the `lru_cache`s on `router._agent_terms` and
`chatbot.available_agent_names`. The effect: a **long-running process** (e.g. the
FastAPI server) reflects added/removed/edited agents on the next request *after a
re-index*, with no restart. The cached client and embedding function are kept; only
catalog-derived state is dropped.

For zero-touch updates, **`scripts/watch_agents.py`** (watchdog) watches `agents/`
and runs `build_index()` + `refresh_catalog_caches()` automatically whenever a `.md`
file is added, modified, or deleted.

## 9. Logging & tracing

Every pipeline module logs through one helper — **`src/logger.py`** (`get_logger(__name__)`)
— so the whole request is traceable. Two handlers are configured once per process:

- **Console** — INFO and above, `[STEP] <message>`: the step-by-step trace
  (new message → intent → agent identified → prompt sent → grounding check → reply)
  a manager can watch live.
- **File** — `logs/agent_chatbot.log`, DEBUG and above, with timestamp/module/level:
  the full record, including the verbose detail (retrieved chunk text, exact prompts)
  that's too noisy for the console. `logs/` is created on first use and is gitignored.

The full prompt text is logged at INFO (intentionally visible in the trace); full
chunk text is logged at DEBUG (file only). **Secrets are never logged** — the API key
is never passed to a logger, only prompt/answer/agent text flows through it; a test
(`tests/test_logging.py`) asserts no record contains a key. On a non-UTF-8 console
(Windows cp1252) the box-drawing glyphs degrade to `?` rather than raising.

## 10. Key dependencies

| Package | Role |
|---------|------|
| `chromadb` | Local persistent vector store (embeddings + metadata). |
| `google-genai` | LLM client (Gemini); optional at runtime. |
| `pyyaml` | Parse `.md` frontmatter. |
| `python-dotenv` | Load `GEMINI_API_KEY` from `.env`. |
| `fastapi` + `uvicorn[standard]` | The HTTP layer (`api.py`). |
| `streamlit` + `requests` | The web UI (`frontend/`); declared in `frontend/requirements.txt`, not the backend's. |
| `watchdog` | Filesystem watcher for `scripts/watch_agents.py` (auto re-index); only needed to run the watcher. |
| `pytest` + `httpx` | Tests (`httpx` backs FastAPI's `TestClient`). |
