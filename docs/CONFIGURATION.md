# Configuration

Every tunable lives in one file: [src/config.py](../agent-recommender/src/config.py).
A few can also be set via environment / `.env`. This doc explains each one — what
it does, its default, and when you'd change it.

> Design rule (PROBLEM_STATEMENT.md §2 & §5): the embedding model, the LLM model,
> paths, and retrieval thresholds are all changeable **in one place** without
> touching the rest of the architecture.

---

## Filesystem paths

| Setting | Default | What it does | When to change |
|---------|---------|--------------|----------------|
| `AGENTS_DIR` | `<repo>/agent-recommender/agents` | Where the catalog `.md` files are read from (by the loader, indexer, router, and `/agents`). | If you relocate the catalog. Otherwise leave it. |
| `CHROMA_PATH` | `<repo>/agent-recommender/.chroma` | Where the persistent ChromaDB store is written/read. Gitignored. | To keep multiple stores, or point at a shared location. Tests override this to a temp dir. |

## ChromaDB store

| Setting | Default | What it does | When to change |
|---------|---------|--------------|----------------|
| `SUMMARY_COLLECTION` | `"agent_summaries"` | Name of the coarse, one-record-per-agent collection (recommendation path). | Rarely. If you rename it, re-index. |
| `SECTION_COLLECTION` | `"agent_sections"` | Name of the fine, one-record-per-section collection (info/RAG path). | Rarely. If you rename it, re-index. |
| `DISTANCE_SPACE` | `"cosine"` | Distance metric set on each collection at index time. Keeps distance in `[0,2]` so `similarity = 1 − distance` is well defined, which is what `Hit.score` reports. | Only if you switch embedding models and have a reason to prefer another metric. Re-index after changing. |

> Changing any store setting means the on-disk store no longer matches the config —
> **re-run `python app.py index`** to rebuild.

> The Chroma client, embedding function, and collection handles are cached as
> process-level singletons in `src/store.py` (so they're not re-created per query).
> `build_index()` calls `store.refresh_catalog_caches()` at the end, so a
> long-running server picks up catalog changes after a re-index without a restart;
> the client re-opens automatically if `CHROMA_PATH` changes (as tests do).

## Retrieval limits (`k`)

| Setting | Default | What it does | When to change |
|---------|---------|--------------|----------------|
| `TOP_K` | `4` | General default number of results. (The paths below use their own more specific values.) | Tuning recall vs. noise broadly. |
| `RECOMMEND_TOP_K` | `3` | How many agent-summary hits the recommendation path retrieves and ranks. | Raise to surface more candidates in a bigger catalog; lower to be stricter. |
| `INFO_TOP_K` | `5` *(defined in `src/info.py`, not `config.py`)* | How many section chunks the info/RAG path retrieves. | Raise if answers miss context spread across sections; lower to tighten grounding. |

## Recommendation thresholds

These were **calibrated against the current catalog's** default-embedding scores:
clear matches land ~0.5–0.8 with a wide gap to the runner-up; out-of-scope queries
top out below ~0.1.

| Setting | Default | What it does | When to change |
|---------|---------|--------------|----------------|
| `NO_MATCH_SCORE` | `0.15` | If the top hit (for an *unfiltered* query) scores below this, the bot says "no clear fit" and lists the catalog instead of guessing. | If real queries are wrongly rejected, **lower** it; if junk queries get matched, **raise** it. A metadata filter bypasses this floor (a filter is strong evidence of intent). |
| `AMBIGUITY_DELTA` | `0.07` | If a runner-up is within this score of the top hit, both are returned as a shortlist (`ambiguous=True`) instead of forcing one pick. | **Widen** to ask for clarification more often; **narrow** to commit to a single pick more often. |

> If you **swap the embedding model**, these numbers no longer mean the same thing —
> different models produce different score distributions. Re-calibrate by checking
> the scores a few known queries return, then adjust.

## Models

| Setting | Default | What it does | When to change |
|---------|---------|--------------|----------------|
| `MODEL` | `"gemini-2.5-flash"` | The LLM used for answer/explanation prose (via `src/llm.py`). Reads `GEMINI_API_KEY`. | To use a different Gemini model. Switching providers means editing `src/llm.py` too. |
| `EMBEDDING_MODEL` | `"chroma-default"` | A label noting which embedding function is used. The actual function is `store.get_embedding_function()` (re-exported by `index`) → ChromaDB's built-in `all-MiniLM-L6-v2`, which runs **locally, no API key**. It's built once per process and cached. | To swap embeddings, edit `get_embedding_function()` in `src/store.py` (one place), then **re-index** and re-calibrate the thresholds above. |

## Environment / `.env`

Copy `.env.example` → `.env` (gitignored). Recognized keys:

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `GEMINI_API_KEY` | **Optional** | Enables LLM-written prose. Without it, every path falls back to deterministic grounded output and the app + tests still run fully. Get one at <https://aistudio.google.com/apikey>. |

`.env.example` also lists commented optional overrides (`MODEL`, `EMBEDDING_MODEL`,
`TOP_K`) as documentation of intent. **Note:** `src/config.py` currently sets these
as constants, so editing `config.py` is the reliable way to change them today.

---

## "I changed a setting — what do I re-run?"

| You changed… | Do this |
|--------------|---------|
| Paths, collection names, distance space, embeddings | `python app.py index` (rebuild the store), then `pytest`. |
| `RECOMMEND_TOP_K`, `INFO_TOP_K`, thresholds | Nothing to rebuild — just restart the chatbot/API. Re-run `pytest`. |
| `MODEL` / `GEMINI_API_KEY` | Just restart the chatbot/API. `python scripts/verify_llm.py` to eyeball LLM-on vs. off. |
