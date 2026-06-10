# Frontend — Streamlit chat UI (Phase 8)

A thin chat UI for the Agent Recommender & Q&A Chatbot. It talks to the FastAPI
backend (`api.py`) **only over HTTP** — it never imports the `src` core — so the
core stays interface-decoupled (PROBLEM_STATEMENT.md §7) and this UI could be
swapped for any other client without touching the backend.

```
frontend/
├── app_ui.py          # the Streamlit app (rendering + session state)
├── api_client.py      # thin HTTP wrapper: call_chat(), fetch_agents(), check_health()
├── requirements.txt   # streamlit, requests
├── README.md          # this file
└── tests/
    └── test_ui.py     # mocks the HTTP layer; no live server needed
```

## What it does

- **Chat** — `st.chat_input` + `st.chat_message`, with the conversation kept in
  `st.session_state` (multi-turn history, shown in order). Each message is POSTed
  to `/chat` and the reply rendered, with a spinner while waiting.
- **Sidebar** — a configurable **API base URL** (default `http://localhost:8000`),
  a **🟢/🔴 health indicator** from `GET /health` (also showing whether an LLM key
  is configured), a live **agent list** from `GET /agents`, a **Use LLM** toggle
  passed through to `/chat`, and a **Clear chat** button.
- **Example prompts** — one-click buttons for the three behaviors: a
  recommendation, an info lookup, and a missing-data (`TBD`) case.
- **Fails soft** — if the backend is unreachable or returns a non-200, the UI
  shows a clear error (and how to start the API) instead of crashing. The UI
  makes no grounding decisions; it renders whatever `/chat` returns.

## Run the full demo

Two terminals, with the project's virtual environment active in each.

**Terminal 1 — backend** (from the repo root, `agent-recommender/`):

```bash
python app.py index            # only if .chroma/ isn't built yet
uvicorn api:app --port 8000
```

**Terminal 2 — frontend**:

```bash
cd frontend
pip install -r requirements.txt
streamlit run app_ui.py
```

Streamlit opens at <http://localhost:8501>. If the backend isn't up yet, the
sidebar shows a red "Backend down" indicator with the command to start it; the
app keeps running and recovers automatically once the API is reachable.

> Point the UI at a different backend by changing the **API base URL** field in
> the sidebar (no restart needed).

## Tests

`tests/test_ui.py` mocks the HTTP layer (`requests.get` / `requests.post`), so it
runs without a live server or Streamlit session:

```bash
# from agent-recommender/
pytest frontend/tests/test_ui.py     # or just `pytest` to run the whole suite
```
