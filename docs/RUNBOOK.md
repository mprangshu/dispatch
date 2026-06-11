# Runbook

Operational guide: how to bring the system up for a demo, what the LLM toggle
does in practice, how it behaves under rate limits, and what to check when
something looks wrong.

> **Status note.** All three interfaces exist and run today: the CLI (`app.py`),
> the HTTP API (`api.py`), and the **Streamlit web UI (`frontend/`)**. Demo via
> whichever you like — the CLI is the one-terminal path, the API's `/docs` gives a
> clickable Swagger UI for free, and the Streamlit UI is the full chat experience.

All commands run from `agent-recommender/` with the venv active.

> **Setup is owned by [INSTALL.md](INSTALL.md)** — do steps 1–7 there first (venv,
> pip, optional `.env`, and `python app.py index` to build the store). This runbook
> assumes an installed, indexed project and covers only running/demoing it.

---

## The demo sequence

### Option A — CLI demo (simplest, one terminal)
```bash
python app.py
```
Then type:
```
you> I need to automate UI tests from a live URL
you> What are the inputs to Test Data Provisioning?
you> What hardware does the User Story Analyser need?     # honest "I don't have that"
you> hi                                                   # clarify
exit
```

### Option B — API demo (two terminals)

**Terminal 1 — backend:**
```bash
uvicorn api:app --reload --port 8000
```
Open `http://localhost:8000/docs` for a clickable Swagger UI, or:
```bash
curl -s localhost:8000/health
curl -s localhost:8000/agents
curl -s localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"I need to automate UI tests from a live URL"}'
```

**Terminal 2 — Streamlit web UI:**
```bash
cd frontend
pip install -r requirements.txt      # first time only: streamlit + requests
streamlit run app_ui.py              # opens http://localhost:8501
```
The UI talks to the backend strictly over HTTP. If the API isn't up yet, the
sidebar shows a red "Backend down" indicator with the command to start it, and
recovers automatically once the API is reachable. Point it at a different backend
via the **API base URL** field in the sidebar (no restart needed). Full detail:
[frontend/README.md](../agent-recommender/frontend/README.md).

### Recommended order for a live demo
1. `python app.py index` (do this *before* the audience arrives — it's the slow step).
2. Start `uvicorn` (Terminal 1).
3. Show `/health` and `/agents`, then a few `/chat` calls via `/docs`.
4. Start Streamlit in Terminal 2 and chat through the UI (the headline experience).

---

## LLM toggle behavior

Two independent things control LLM use:

| Lever | Where | Effect |
|-------|-------|--------|
| `GEMINI_API_KEY` in `.env` | environment | **Present** → LLM calls can succeed. **Absent** → every path uses the deterministic grounded fallback. |
| `use_llm` flag | `handle(..., use_llm=)`, `POST /chat` body `use_llm` | `true` (default) → use the LLM for answer/explanation prose. `false` → force the deterministic path even if a key is set. |

Key facts to remember during a demo:

- **Intent routing never uses the LLM** — it's always the deterministic router.
  `use_llm` only affects the *answer/explanation wording*.
- **Facts and grounding are identical** with the LLM on or off; only prose richness
  changes. Verify live with `python scripts/verify_llm.py` (prints on-vs-off side
  by side).
- **No key is a valid state.** With no key, `use_llm=true` silently behaves like
  `use_llm=false`. Nothing breaks. `GET /health` shows `llm_available: false`.

## Rate-limit / failure fallback

`llm.generate()` returns `None` on **any** failure — no key, SDK missing, network
error, or quota exhaustion (free-tier Gemini returns **HTTP 429**) — and it never
raises. Callers then fall back to the deterministic grounded path.

**Symptom:** the LLM is "on" (key set) but answers suddenly read like the terse
offline fallback ("From the … documentation (Inputs): …").
**Likely cause:** the Gemini quota window is exhausted (429).
**Fix:** wait for the quota window to reset, or use a key with higher limits. No
restart needed — the wrapper recovers automatically on the next successful call.

---

## When something looks wrong — checklist

| Symptom | Check / Fix |
|---------|-------------|
| `python app.py` says the catalog isn't indexed | Run `python app.py index` first. The REPL guards this instead of crashing. |
| `/chat` replies but can't find any agent content | Store not built or empty → `python app.py index`. (`/health` and `/agents` work without it.) |
| Every answer looks like the deterministic fallback | Either no `GEMINI_API_KEY`, or quota hit (429). Check `GET /health` → `llm_available`. |
| `ModuleNotFoundError: chromadb` / `yaml` / `fastapi` | venv not active or deps not installed → `pip install -r requirements.txt`. |
| `uvicorn` / `fastapi` not found | Same — re-install deps with the venv active. |
| New agent `.md` not showing up in answers | Re-index: `python app.py index`. (`GET /agents` reads live and updates without re-index; **retrieval** needs the re-index.) |
| A new `.md` breaks loading | `pytest tests/test_loader.py` — it runs against the real catalog and points at the malformed file. Check the YAML frontmatter. |
| Tests fail on a fresh machine, first run only | The embedding model download may have been interrupted — re-run `pytest` once it completes (~1 min). |
| PowerShell won't activate the venv | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then re-activate. |
| CORS error from a browser front end | CORS is open (`*`) by design; if locked down for prod, add your front-end origin to `api.py`. |

## Health & sanity probes

```bash
curl -s localhost:8000/health     # {"status":"ok","llm_available":<bool>}
curl -s localhost:8000/agents     # the live catalog — confirms agents/ is readable
pytest -q                         # full offline verification (95 passing)
python scripts/verify_llm.py      # LLM on-vs-off A/B (needs store built)
```

## Safe to re-run

- `python app.py index` is **idempotent** — it drops and rebuilds both collections
  cleanly. Re-run any time you add/edit/remove an agent file.
- Restarting `uvicorn` is harmless; it reads the same store and live catalog.
- No data is mutated by chatting — the bot only reads. There's no user state or
  persistence beyond the Chroma store (PROBLEM_STATEMENT.md §7).
