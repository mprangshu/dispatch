# Installation Guide

How to get the **Agent Recommender & Q&A Chatbot** running after cloning from
GitHub.

> **Project status: backend complete (Phases 1–7), all 84 tests passing.** The
> catalog loader + data model (Phase 1), the ChromaDB indexer + retriever
> (Phase 2), the recommendation path (Phase 3, `src/recommender.py`), the intent
> router + RAG info path (Phase 4, `src/router.py` + `src/info.py`), the
> orchestration + CLI (Phase 5, `src/chatbot.py` + `app.py`), the live-LLM
> activation/verification (Phase 6, `scripts/verify_llm.py` + `tests/test_llm.py`),
> and the FastAPI backend (Phase 7, `api.py`) are all implemented and tested. The
> chatbot is runnable end to end as a CLI (`python app.py index`, then
> `python app.py`) and over HTTP (`uvicorn api:app --port 8000`). Phase 8 — a
> Streamlit UI over the API — is the only remaining piece.

---

## 1. Prerequisites

- **Python 3.11 or newer** — check with `python --version`.
- **git** — to clone the repository.
- An **LLM API key** (Google Gemini by default) — used for LLM-generated
  recommendation explanations and the chatbot's grounded answers. Optional:
  every path falls back to deterministic, grounded behavior without it, so the
  chatbot and the tests run fully offline. Get one at
  <https://aistudio.google.com/apikey>.

## 2. Clone the repository

```bash
git clone <your-repo-url>
cd agent-recommender
```

> If the project lives in a subfolder of the repo, `cd` into the
> `agent-recommender/` directory — it's the one containing `requirements.txt`.

## 3. Create and activate a virtual environment

A virtual environment keeps dependencies isolated from your system Python. The
`.venv/` folder is gitignored.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> If PowerShell blocks the activation script with an execution-policy error,
> run once per session:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

**Windows (cmd):**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now show `(.venv)`. To leave it later, run `deactivate`.

## 4. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs `chromadb`, `google-genai`, `pyyaml`, `python-dotenv`, `fastapi`,
`uvicorn[standard]` (the HTTP backend), `pytest`, and `httpx` (used by the API
tests).

## 5. Configure your API key

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` and set `GEMINI_API_KEY` to your key. `.env` is gitignored,
so your secret never gets committed. (You can skip this step if you only want to
run the loader/tests or use the recommender with its deterministic fallback
explanations.)

## 6. Verify the install — run the tests

```bash
pytest
```

You should see the suite pass (84 passed). These run against the real agent
files in `agents/` — the loader tests confirm the catalog parses correctly, the
indexer/retriever tests build a throwaway ChromaDB store and query it, the
recommender tests check the recommendation path (clear match, ambiguous
shortlist, metadata-filtered query, and no-match), the router/info tests check
intent classification and the grounded RAG answers (including the honest "I
don't have that" for `TBD` fields), the chatbot tests drive `handle()` end to
end across every acceptance criterion (recommendation, grounded answer, honest
"not available", vague→clarify, and new-agent discoverability after re-indexing),
the LLM guardrail tests (mocked, so no key needed) prove the grounding gate holds
even with the LLM on, and the API tests exercise the FastAPI endpoints — so a
green run confirms the install, the catalog, the vector store, the full
recommendation/info/orchestration logic, and the HTTP layer all work.

> The first run downloads the default embedding model (a few tens of MB) and can
> take ~1 minute; subsequent runs are fast.

## 7. Index the catalog

This builds the local ChromaDB store from the `.md` files in `agents/`. It
writes to `.chroma/` (gitignored) and is safe to re-run — each run rebuilds the
store cleanly from the current files, so adding or editing an agent only needs a
re-index, no code changes.

```bash
python app.py index
```

> `python -m src.index` does the same thing — `python app.py index` is just the
> convenience wrapper. The first run downloads the embedding model (see the note
> in step 6).

## 8. Run the chatbot

```bash
python app.py
```

This starts an interactive REPL. Describe a task to get a recommendation, or ask
a question about a specific agent; type `exit` (or press Ctrl-D) to quit. If you
haven't indexed yet, the REPL tells you to run `python app.py index` first.

```text
you> I need to automate UI tests from a live URL
I'd recommend **Test Script Generator Agent**. …

you> What are the inputs to Test Data Provisioning?
From the Test Data Provisioning documentation (Inputs):
| User Story ID | Yes | … |
_Source: Test Data Provisioning — Inputs_

you> What hardware does the User Story Analyser need?
I don't have that information. … it's currently marked TBD / not specified.
```

## 9. Run the HTTP API (optional)

The same core is exposed over HTTP by the FastAPI backend in `api.py` — useful
for a web/UI front end (Phase 8) or any external caller. Index first (step 7),
then:

```bash
uvicorn api:app --reload --port 8000
```

Endpoints (interactive docs at <http://localhost:8000/docs>):

- `POST /chat` — body `{ "message": "...", "use_llm": true }` → `{ "reply": "..." }`
- `GET /agents` — the live catalog as JSON
- `GET /health` — `{ "status": "ok", "llm_available": true|false }`

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python` not found / wrong version | Use `python3`, or install Python 3.11+ and ensure it's on your PATH. |
| `ModuleNotFoundError: yaml` / `chromadb` | The venv isn't active or deps aren't installed — redo steps 3–4. |
| PowerShell won't run `Activate.ps1` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then re-activate. |
| `pytest` runs against system Python | Activate the venv first, or call `python -m pytest`. |
| API key errors when running the chatbot | Confirm `.env` exists and `GEMINI_API_KEY` is set (step 5). |
| LLM answers silently look like the offline fallback | The free-tier Gemini quota may be exhausted (HTTP 429); the wrapper falls back automatically. Wait for the quota window to reset or use a key with higher limits. |
| `uvicorn`/`fastapi` not found | Re-run `pip install -r requirements.txt` with the venv active (step 4). |

See [PROBLEM_STATEMENT.md](../PROBLEM_STATEMENT.md) for the full specification
and [README.md](README.md) for a project overview.
