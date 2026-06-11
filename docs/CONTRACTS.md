# Internal Contracts

These are the Python interface signatures the modules agree on. They are the
**single source of truth for parallel work**: as long as each module honors its
contract, the others can stub it and develop independently. **Do not change a
signature without team agreement** (PROBLEM_STATEMENT.md working agreements;
mirrors PROJECT_HANDOFF.md §7).

The public surface is re-exported from
[src/\_\_init\_\_.py](../agent-recommender/src/__init__.py):
`handle`, `recommend`, `answer_question`, `detect_intent`, `build_index`.

---

## Data types

### `Agent` — produced by Phase 1, consumed by everyone
[src/models.py](../agent-recommender/src/models.py)

```python
@dataclass
class Agent:
    agent_id: str
    name: str
    domain: str
    tags: list[str]
    autonomy_default: str
    autonomy_supported: list[str]
    triggers: list[str]              # may be empty = "not specified"
    sections: dict[str, str]         # "Overview" -> raw markdown body
    source_path: str

    def get_section(name: str) -> str | None   # case-insensitive; None if absent
    def summary_text() -> str                   # name + Overview + tags (for embedding)
```

List fields stay **lists** here; flattening to Chroma metadata is the indexer's job.

### `Hit` — produced by the retriever, consumed by both paths
[src/retriever.py](../agent-recommender/src/retriever.py)

```python
@dataclass
class Hit:
    agent_id: str
    name: str
    text: str
    score: float            # cosine similarity in [0, 1], higher = closer
    section: str | None     # set for section hits; None for agent-summary hits
    metadata: dict          # the stored Chroma metadata (flattened frontmatter)
```

---

## Ingestion & store (Phase 1–2)

```python
# loader.py
load_agent(path: str | Path) -> Agent
load_agents(directory: str | Path) -> list[Agent]   # sorted, deterministic

# index.py
build_index(agents_dir=None, chroma_path=None) -> dict
# Rebuilds BOTH collections cleanly, then calls store.refresh_catalog_caches(). Returns:
#   { "agents": int, "summary_records": int, "section_records": int, "chroma_path": str }

# store.py — shared, process-level singletons (also re-exported by index.py)
get_client(path=None)                  # cached persistent Chroma client; re-opens on a path change
get_embedding_function()               # the single swap point for embeddings (cached)
get_summary_collection(client=None)    # cached handle to the agent_summaries collection
get_section_collection(client=None)    # cached handle to the agent_sections collection
refresh_catalog_caches()               # after a re-index: drop cached collections + clear
                                       #   router._agent_terms / chatbot.available_agent_names lru_caches
```

## Retriever (Phase 2 provides; Phases 3 & 4 consume)

```python
search_agents(query: str, k: int = 3, where: dict | None = None) -> list[Hit]
search_sections(query: str, k: int = 5, where: dict | None = None) -> list[Hit]
```

- Results are ordered **best-first**.
- `where` is a Chroma metadata filter. Scalars filter directly
  (`{"autonomy_default": "L4"}`); compose with `$and`
  (`{"$and": [{"agent_id": "..."}, {"section": "Inputs"}]}`).
- **Metadata shape** (set by the indexer): list frontmatter fields are flattened to
  comma-joined strings — `tags`, `autonomy_supported` (`"L1, L2, L3"`), `triggers`
  (`""` when unspecified, with a companion bool `triggers_specified`). Scalars:
  `agent_id`, `name`, `domain`, `autonomy_default`, and `section` (section records
  only).

## Recommendation path (Phase 3 provides; Phase 5 consumes)
[src/recommender.py](../agent-recommender/src/recommender.py)

```python
recommend(query: str, *, k=None, use_llm=True, search_fn=None) -> dict
# returns { "agents": list[Hit], "explanation": str, "ambiguous": bool }
```

- One clear best → `agents=[hit]`, `ambiguous=False`.
- Several comparable → `agents=[shortlist]`, `ambiguous=True`.
- No fit / out of scope → `agents=[]`, `ambiguous=False`, honest explanation.
- `search_fn` is **injectable** (defaults to `retriever.search_agents`) so callers
  and tests can stub retrieval against this contract.
- Helper: `detect_filter(query) -> dict | None` ("fully autonomous" → `L4`; explicit
  `L1`–`L4` direct).

## Intent router (Phase 4 provides; Phase 5 consumes)
[src/router.py](../agent-recommender/src/router.py)

```python
detect_intent(query: str, *, use_llm=False) -> "recommend" | "info" | "clarify"
find_agent(query: str) -> str | None     # agent_id named in the query, catalog-driven
```

- Deterministic rules by default. `use_llm=True` adds an LLM pass in front, but its
  output is only trusted when it's one of the three valid labels; otherwise the
  rules decide. Empty/very-short/vague → `clarify`.
- **Note:** `chatbot.handle` calls `detect_intent` with the default
  (deterministic) — it does not enable the LLM pass for routing.

## Info / RAG path (Phase 4 provides; Phase 5 consumes)
[src/info.py](../agent-recommender/src/info.py)

```python
answer_question(query: str, *, k=None, use_llm=True, search_fn=None) -> dict
# returns { "answer": str, "sources": list[Hit], "grounded": bool }
```

- `grounded=False` (with an honest "I don't have that information") when the answer
  isn't in the retrieved text — e.g. `Deployment` fields that are `TBD`. **This is a
  hard guarantee, enforced before the LLM is called.**
- `search_fn` injectable (defaults to `retriever.search_sections`).
- Helper: `detect_section(query) -> str | None` (maps question words to a section
  header: `Inputs`, `Outputs`, `Autonomy Level`, `Triggers`, `Deployment`,
  `Limitations`, `Overview`).

## LLM wrapper (shared infra; used by Phases 3 & 4)
[src/llm.py](../agent-recommender/src/llm.py)

```python
generate(prompt: str, system: str | None = None, model: str | None = None) -> str | None
available() -> bool      # True when GEMINI_API_KEY is set
```

- **`generate` returns `None` on any failure and never raises** — the contract every
  caller relies on to fall back deterministically. There is exactly **one** LLM
  client in the codebase; reuse this wrapper, don't create a second.

## Orchestration (Phase 5 provides)
[src/chatbot.py](../agent-recommender/src/chatbot.py)

```python
handle(message: str, *, use_llm=True) -> str   # detect_intent -> route -> format reply
available_agent_names() -> tuple[str, ...]      # live catalog names, for edge replies
```

- The path functions and the router are **module-level names** in `chatbot.py` so
  tests can monkeypatch them (`chatbot.recommend`, `chatbot.answer_question`,
  `chatbot.detect_intent`).
- `use_llm` threads into the recommend/info paths only.

## HTTP layer (Phase 7)
[api.py](../agent-recommender/api.py) — mirrors `handle` over HTTP. Shapes documented
in [API_REFERENCE.md](API_REFERENCE.md). `POST /chat` ⇔ `handle(message, use_llm=...)`.

---

## Why these are frozen

Each module was built in its own session against these signatures, stubbing its
dependencies. If a contract must change, raise it with the team and update this doc,
the consumers, and the tests together — never change it locally and silently.
