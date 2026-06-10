# Installation Guide

How to get the **Agent Recommender & Q&A Chatbot** running after cloning from
GitHub.

> **Project status:** Phase 1 (the catalog loader + data model) is implemented
> and tested. The indexer, retriever, router, and chatbot are still stubs, so
> the only thing runnable end-to-end today is the test suite. Steps marked
> _(coming soon)_ describe the intended workflow and don't work yet.

---

## 1. Prerequisites

- **Python 3.11 or newer** — check with `python --version`.
- **git** — to clone the repository.
- An **LLM API key** (Google Gemini by default) — only needed for the chatbot
  paths, not for the loader/tests. Get one at
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
run the loader and tests.)

## 6. Verify the install — run the tests

```bash
pytest
```

You should see the loader tests pass (10 passed). These run against the real
agent files in `agents/`, so a green run confirms both the install and that the
catalog parses correctly.

## 7. Index the catalog _(coming soon)_

Once the indexer is implemented, this builds the local ChromaDB store from the
`.md` files in `agents/`. It writes to `.chroma/` (gitignored) and is safe to
re-run.

```bash
# python app.py index      # not implemented yet
```

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
