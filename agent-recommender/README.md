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

> **Status:** Phases 1–3 are implemented and tested. Phase 1 = the catalog
> loader + data model; Phase 2 = the ChromaDB indexer (`src/index.py`) and
> retriever (`src/retriever.py`); Phase 3 = the recommendation path
> (`src/recommender.py`), which returns the best-fitting agent(s) for a described
> need with a grounded explanation. You can build the store with
> `python -m src.index`, query it via `src.retriever`, and get a recommendation
> via `src.recommender.recommend(query)`. Explanations use the configured LLM
> (set `GEMINI_API_KEY`) but fall back to a deterministic template when it's
> unavailable. The router and chatbot are still stubs, so the `app.py` REPL is
> not runnable yet (that's Phase 5 — see PROBLEM_STATEMENT.md section 6 for the
> build order).
