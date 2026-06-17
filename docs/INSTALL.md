# Installation

First-time setup: get the **Agent Recommender & Q&A Chatbot** running after
cloning. This doc owns the **setup steps** only. For running a demo, the
LLM toggle, and troubleshooting, see [RUNBOOK.md](RUNBOOK.md); for build status,
[PROJECT_HANDOFF.md](PROJECT_HANDOFF.md).

All commands run from the `agent-recommender/` directory (the one containing
`requirements.txt`).

---

## 1. Prerequisites

- **Python 3.11 or newer** — check with `python --version`.
- **git** — to clone the repository.
- An **LLM API key** (Google Gemini by default) — **optional**. It enables
  LLM-written prose; without it every path falls back to deterministic, grounded
  behavior, so the app and the tests run fully offline. Get one at
  <https://aistudio.google.com/apikey>.

## 2. Clone and enter the project

```bash
git clone <your-repo-url>
cd <repo>/agent-recommender
```

## 3. Create and activate a virtual environment

The `.venv/` folder is gitignored.

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
> If PowerShell blocks the activation script, run once per session:
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

Your prompt should now show `(.venv)`. Leave it later with `deactivate`.

## 4. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs `chromadb`, `google-genai`, `pyyaml`, `python-dotenv`, `fastapi`,
`uvicorn[standard]` (the HTTP backend), `watchdog` (for the optional
auto-reindex watcher), `pytest`, and `httpx` (used by the API tests).

## 5. Configure your API key (optional)

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
# macOS / Linux
cp .env.example .env
```

Open `.env` and set `GEMINI_API_KEY`. `.env` is gitignored. Skip this if you only
want the deterministic, offline behavior. (Full detail on the key and other
tunables: [CONFIGURATION.md](CONFIGURATION.md).)

## 6. Verify the install

```bash
pytest
```

You should see **101 passed**. The tests run offline and need no API key — what
each one covers is in [TESTING.md](TESTING.md).

> **First-run note (applies to step 6 and 7):** the first time anything builds or
> queries the store, ChromaDB downloads its default embedding model
> (`all-MiniLM-L6-v2`, a few tens of MB, ~1 min). Subsequent runs are fast.

## 7. Index the catalog

Builds the local ChromaDB store from the `.md` files in `agents/` (writes to
`.chroma/`, gitignored). Safe to re-run — each run rebuilds cleanly.

```bash
python app.py index
```

> Re-run this whenever you add/edit/remove an agent `.md`. To do it automatically,
> run the watcher instead: `python scripts/watch_agents.py` (needs `watchdog`) —
> it re-indexes and refreshes caches on every change. See [RUNBOOK.md](RUNBOOK.md).

## 8. Run it

```bash
python app.py            # interactive chat REPL (CLI)
```

Describe a task to get a recommendation, or ask about a specific agent; type
`exit` (or Ctrl-D) to quit. If you haven't indexed yet, the REPL tells you to run
`python app.py index` first.

To serve the same core over HTTP instead, see [RUNBOOK.md](RUNBOOK.md) and
[API_REFERENCE.md](API_REFERENCE.md):

```bash
uvicorn api:app --reload --port 8000
```

For the **Streamlit web UI**, start the API above, then in a second terminal
install the UI's own dependencies and launch it (full detail in
[frontend/README.md](../agent-recommender/frontend/README.md)):

```bash
cd frontend
pip install -r requirements.txt      # streamlit + requests
streamlit run app_ui.py              # opens http://localhost:8501
```

---

For demoing, the LLM on/off behavior, rate-limit fallback, and a full
symptom→fix table, go to [RUNBOOK.md](RUNBOOK.md).
