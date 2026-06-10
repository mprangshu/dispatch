# Installation Guide

How to get the **Agent Recommender & Q&A Chatbot** running after cloning from
GitHub.

> **Project status:** Phases 1–3 are implemented and tested — the catalog
> loader + data model (Phase 1), the ChromaDB indexer + retriever (Phase 2), and
> the recommendation path (Phase 3, `src/recommender.py`). The catalog can be
> indexed today with `python -m src.index`. The router and chatbot are still
> stubs, so the `app.py` REPL isn't runnable yet. Steps marked _(coming soon)_
> describe the intended workflow and don't work yet.

---

## 1. Prerequisites

- **Python 3.11 or newer** — check with `python --version`.
- **git** — to clone the repository.
- An **LLM API key** (Google Gemini by default) — used for LLM-generated
  recommendation explanations and (later) the chatbot paths. Optional: the
  recommender falls back to a deterministic explanation without it, and the
  loader/tests don't need it. Get one at <https://aistudio.google.com/apikey>.

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

This installs `chromadb`, `google-genai`, `pyyaml`, `python-dotenv`, and
`pytest`.

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

You should see the suite pass (27 passed). These run against the real agent
files in `agents/` — the loader tests confirm the catalog parses correctly, the
indexer/retriever tests build a throwaway ChromaDB store and query it, and the
recommender tests check the recommendation path (clear match, ambiguous
shortlist, metadata-filtered query, and no-match) — so a green run confirms the
install, the catalog, the vector store, and the recommendation logic all work.

> The first run downloads the default embedding model (a few tens of MB) and can
> take ~1 minute; subsequent runs are fast.

## 7. Index the catalog

This builds the local ChromaDB store from the `.md` files in `agents/`. It
writes to `.chroma/` (gitignored) and is safe to re-run — each run rebuilds the
store cleanly from the current files, so adding or editing an agent only needs a
re-index, no code changes.

```bash
python -m src.index
```

> A convenience `python app.py index` subcommand will wrap this in Phase 5.

## 8. Run the chatbot _(coming soon)_

```bash
# python app.py            # not implemented yet
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python` not found / wrong version | Use `python3`, or install Python 3.11+ and ensure it's on your PATH. |
| `ModuleNotFoundError: yaml` / `chromadb` | The venv isn't active or deps aren't installed — redo steps 3–4. |
| PowerShell won't run `Activate.ps1` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then re-activate. |
| `pytest` runs against system Python | Activate the venv first, or call `python -m pytest`. |
| API key errors when running the chatbot | Confirm `.env` exists and `GEMINI_API_KEY` is set (step 5). |

See [PROBLEM_STATEMENT.md](../PROBLEM_STATEMENT.md) for the full specification
and [README.md](README.md) for a project overview.
