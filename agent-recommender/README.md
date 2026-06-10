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
pytest                               # verify the install (68 passed)
python app.py index                  # build the ChromaDB store from agents/
python app.py                        # start the chatbot REPL
```

> **Status: complete (Phases 1–5), all 68 tests passing.** The full pipeline is
> built and the chatbot is runnable end to end:
> - **Phase 1** — catalog loader + data model (`src/loader.py`, `src/models.py`).
> - **Phase 2** — ChromaDB indexer (`src/index.py`) + retriever (`src/retriever.py`).
> - **Phase 3** — recommendation path (`src/recommender.py`): best-fitting agent(s)
>   with a grounded explanation.
> - **Phase 4** — intent router (`src/router.py`, `detect_intent`) + RAG info path
>   (`src/info.py`, `answer_question`): answers about an agent grounded strictly in
>   its doc, saying "I don't have that information" rather than guessing when a
>   field is `TBD`.
> - **Phase 5** — orchestration (`src/chatbot.py`, `handle`) + the CLI (`app.py`).
>
> Build the store with `python app.py index`, then chat with `python app.py`.
> Programmatically, the one-call entry point is `src.chatbot.handle(message)`; the
> individual paths (`recommend`, `answer_question`, `detect_intent`) are also
> exported from the `src` package. The LLM paths use the configured model (set
> `GEMINI_API_KEY`) but fall back to deterministic, grounded behavior when it's
> unavailable, so everything runs offline too. See
> [ONBOARDING.md](../ONBOARDING.md) for a full walkthrough and
> [PROBLEM_STATEMENT.md](../PROBLEM_STATEMENT.md) for the spec.
