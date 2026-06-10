# Agent Recommender & Q&A Chatbot

Recommends the best-fitting AI agent for a described need and answers questions
about agents, grounded strictly in a Markdown catalog (no fabricated facts).

See [PROBLEM_STATEMENT.md](../PROBLEM_STATEMENT.md) for the full spec.

## Setup / Run

Full step-by-step setup for cloners lives in [INSTALL.md](INSTALL.md). Quick
version:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows (PowerShell); use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
cp .env.example .env                 # then set GEMINI_API_KEY (optional)
pytest                               # verify the install (84 passed)
python app.py index                  # build the ChromaDB store from agents/
python app.py                        # start the chatbot REPL

# optional — serve the same core over HTTP instead of the CLI:
uvicorn api:app --reload --port 8000 # POST /chat, GET /agents, GET /health (docs at /docs)
```

> **Status: backend complete (Phases 1–7), all 84 tests passing.** The full
> pipeline is built and runnable end to end, both as a CLI and over HTTP:
> - **Phase 1** — catalog loader + data model (`src/loader.py`, `src/models.py`).
> - **Phase 2** — ChromaDB indexer (`src/index.py`) + retriever (`src/retriever.py`).
> - **Phase 3** — recommendation path (`src/recommender.py`): best-fitting agent(s)
>   with a grounded explanation.
> - **Phase 4** — intent router (`src/router.py`, `detect_intent`) + RAG info path
>   (`src/info.py`, `answer_question`): answers about an agent grounded strictly in
>   its doc, saying "I don't have that information" rather than guessing when a
>   field is `TBD`.
> - **Phase 5** — orchestration (`src/chatbot.py`, `handle`) + the CLI (`app.py`).
> - **Phase 6** — LLM activated & verified live against Gemini: an on/off A/B
>   script (`scripts/verify_llm.py`) plus mocked guardrail tests
>   (`tests/test_llm.py`) proving the grounding gate holds with the LLM on.
> - **Phase 7** — FastAPI backend (`api.py`): `POST /chat`, `GET /agents`,
>   `GET /health` over the unchanged core. Run with `uvicorn api:app --port 8000`.
>
> Still to come: **Phase 8** — a Streamlit chat UI calling the API.
>
> Build the store with `python app.py index`, then chat with `python app.py` (or
> start the API with `uvicorn api:app`). Programmatically, the one-call entry point
> is `src.chatbot.handle(message)`; the paths (`recommend`, `answer_question`,
> `detect_intent`) and `build_index` are exported from the `src` package. Intent
> detection uses the deterministic router (no API call); set `GEMINI_API_KEY` for
> LLM-written prose on the answer/explanation, otherwise grounded deterministic
> fallbacks keep everything running offline. See
> [ONBOARDING.md](../ONBOARDING.md) for a full walkthrough and
> [PROBLEM_STATEMENT.md](../PROBLEM_STATEMENT.md) for the spec.
