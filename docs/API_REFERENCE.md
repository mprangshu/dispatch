# API Reference

The HTTP layer over the chatbot core, defined in
[api.py](../agent-recommender/api.py) (Phase 7). It is a **thin pass-through**:
it imports the public surface of `src` and adds no business logic. `POST /chat`
is exactly `chatbot.handle(message, use_llm=...)`.

- **Framework:** FastAPI (ASGI), served with `uvicorn`.
- **Base URL (local):** `http://localhost:8000`
- **Interactive docs:** `http://localhost:8000/docs` (Swagger UI, auto-generated).
- **Content type:** `application/json`.

## Running it

```bash
# from agent-recommender/, venv active, store already built (python app.py index)
uvicorn api:app --reload --port 8000
```

> **Prerequisite:** the ChromaDB store must exist (`python app.py index`) before
> `/chat` queries that hit retrieval will work. `/health` and `/agents` work
> without it.

---

## `POST /chat`

Run one message through the chatbot and get back a single reply string.

**Request body** (`ChatRequest`):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | **yes** | — | The user's message. |
| `use_llm` | boolean | no | `true` | `true` = LLM writes the answer/explanation prose; `false` = forces the deterministic, grounded path (no network). |

```json
{ "message": "I need to automate UI tests from a live URL", "use_llm": true }
```

**Response** `200 OK` (`ChatResponse`):

```json
{ "reply": "I'd recommend **Test Script Generator Agent**. …" }
```

The `reply` is the same string the CLI would print — recommendation text, a
grounded info answer with a `_Source: …_` line, an honest "I don't have that"
for `TBD` fields, or a clarifying question for vague input. See
[DATA_FLOW.md](DATA_FLOW.md) for how the reply is produced.

**Examples**

```bash
# grounded info answer
curl -s localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"What are the inputs to Test Data Provisioning?","use_llm":false}'
# → {"reply":"From the Test Data Provisioning documentation (Inputs): …\n\n_Source: Test Data Provisioning — Inputs_"}

# honest "not available" (TBD field)
curl -s localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"What hardware does the User Story Analyser need?"}'
# → {"reply":"I don't have that information. … marked TBD / not specified."}
```

---

## `GET /agents`

List the live catalog (reads `agents/` on each call — never hard-coded).

**Response** `200 OK` — array of `AgentInfo`:

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Slug, e.g. `test-data-provisioning`. |
| `name` | string | Display name. |
| `domain` | string | e.g. `testing`. |
| `autonomy_default` | string | e.g. `L2`. |
| `tags` | string[] | Keyword tags (a real list, not flattened). |

```bash
curl -s localhost:8000/agents
```
```json
[
  { "agent_id": "test-data-provisioning", "name": "Test Data Provisioning",
    "domain": "testing", "autonomy_default": "L2",
    "tags": ["test-data","provisioning","synthetic-data","tdr","export"] }
]
```

Add an `.md` file to `agents/` and it appears here on the next request — no
restart or code change needed (the data is read live). `/chat` retrieval needs a
re-index (`python app.py index`, or run `scripts/watch_agents.py`); because
`build_index()` calls `store.refresh_catalog_caches()`, a running server then
serves the new agent on its next request **without a restart**.

---

## `GET /health`

Liveness check plus whether an LLM key is configured.

**Response** `200 OK` (`HealthResponse`):

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always `"ok"` when the service is up. |
| `llm_available` | boolean | `true` if `GEMINI_API_KEY` is set (an LLM call *could* succeed). `false` → the app still works via deterministic fallbacks. |

```bash
curl -s localhost:8000/health
# → {"status":"ok","llm_available":false}
```

---

## CORS

CORS is **open to all origins** so a browser/Streamlit front end can call the API
directly:

```python
allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
```

> Because credentials are allowed, Starlette echoes the *request's* `Origin` back
> in `Access-Control-Allow-Origin` rather than a literal `*` (the CORS spec forbids
> `*` together with credentials). Both forms mean the cross-origin call is allowed.
>
> **Production note:** `allow_origins=["*"]` is convenient for local development.
> Before any real deployment, lock it down to your known front-end origin(s).

## Error cases

| Situation | Result |
|-----------|--------|
| `message` missing/empty type | FastAPI/Pydantic returns **422 Unprocessable Entity** with a validation detail (handled by the framework, not custom code). |
| `use_llm` omitted | Defaults to `true`. |
| Store not indexed yet | `/health` and `/agents` still work. A `/chat` query that needs retrieval returns a reply but won't find content; **index first** (`python app.py index`). |
| LLM key missing or quota hit (HTTP 429) | No error surfaced — `llm.generate` returns `None` and the path falls back to deterministic grounded output. `/health` shows `llm_available` per the key. |

There are currently **no authentication** and no rate limiting on the API
(out of scope, PROBLEM_STATEMENT.md §7).

## Contract stability

The endpoint shapes mirror the internal contracts in [CONTRACTS.md](CONTRACTS.md).
`POST /chat` ⇔ `handle`. Treat these request/response shapes as a contract for any
UI built against them; change them only by team agreement.
