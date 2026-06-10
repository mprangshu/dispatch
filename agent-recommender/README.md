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
cp .env.example .env                 # then set GEMINI_API_KEY
pytest                               # verify the install
python -m src.index                  # build the ChromaDB store from agents/
```

> **Status:** Phases 1–2 are implemented and tested. Phase 1 = the catalog
> loader + data model; Phase 2 = the ChromaDB indexer (`src/index.py`) and
> retriever (`src/retriever.py`). You can build the store with
> `python -m src.index` and query it via `src.retriever`. The router and
> chatbot are still stubs, so the `app.py` REPL is not runnable yet (that's
> Phase 5 — see PROBLEM_STATEMENT.md section 6 for the build order).
