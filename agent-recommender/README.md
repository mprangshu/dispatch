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
```

> **Status:** Phase 1 (catalog loader + data model) is implemented and tested.
> The indexer, retriever, router, and chatbot are still stubs — `app.py index`
> and `app.py` are not runnable yet (see PROBLEM_STATEMENT.md section 6 for the
> build order).
