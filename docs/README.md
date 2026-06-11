# Agent Recommender & Q&A Chatbot — Documentation

**All project documentation lives in this folder.** This page is the index and a
one-paragraph overview; every other topic has exactly one home, linked below.

> **What it is.** A chatbot over a catalog of AI agents — usable from the CLI, an
> HTTP API, or a Streamlit web UI — each agent defined by one Markdown file in
> [`agent-recommender/agents/`](../agent-recommender/agents/).
> It **recommends** the best-fitting agent for a described need, or **answers
> questions** about an agent grounded strictly in its doc — never inventing facts,
> and honestly saying *"I don't have that information"* when a field is `TBD`. No
> API key is required to run it: every LLM call has a deterministic, grounded
> fallback. **Status: complete (Phases 1–8) — core, CLI, HTTP API, and Streamlit
> web UI all built; 95 tests passing** — details in
> [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md).

---

## New here? Read in this order

[ONBOARDING.md](ONBOARDING.md) is the orientation map (reading order + code map +
"where to look when…"). The short path:
[PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) → [ARCHITECTURE.md](ARCHITECTURE.md) →
[DATA_FLOW.md](DATA_FLOW.md) → [CONTRACTS.md](CONTRACTS.md) →
[INSTALL.md](INSTALL.md).

## All documents

### Understand the system
| Doc | Owns |
|-----|------|
| [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) | The behavior spec — *what* it must do, plus acceptance criteria & known gaps. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Two-collection ChromaDB design, RAG vs. semantic-search split, LLM-optional pattern, `src → api → UI` layers, repo layout. |
| [DATA_FLOW.md](DATA_FLOW.md) | How one message travels input → intent → retrieval → LLM/fallback → reply, with the grounding gate. |
| [ONBOARDING.md](ONBOARDING.md) | Reading order, code map, "where to look when…", task→doc pointers. |

### Build & run
| Doc | Owns |
|-----|------|
| [INSTALL.md](INSTALL.md) | First-time setup: venv → pip → key → index → run. |
| [CONFIGURATION.md](CONFIGURATION.md) | Every tunable in `src/config.py`: what it does and when to change it. |
| [RUNBOOK.md](RUNBOOK.md) | Demo sequence, LLM toggle, rate-limit fallback, full troubleshooting table. |

### APIs & contracts
| Doc | Owns |
|-----|------|
| [API_REFERENCE.md](API_REFERENCE.md) | FastAPI endpoints (`POST /chat`, `GET /agents`, `GET /health`): shapes, errors, CORS. |
| [CONTRACTS.md](CONTRACTS.md) | The internal Python signatures that must not change without team agreement. |
| [frontend/README.md](../agent-recommender/frontend/README.md) | The Streamlit web UI: what it does, how to run it, and its HTTP-only contract with the API. |

### Data, testing, project state
| Doc | Owns |
|-----|------|
| [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md) | The exact `.md` schema for an agent file, and the `TBD` behavior. |
| [TESTING.md](TESTING.md) | Test layout, the `use_llm=False` / `search_fn=` injection patterns, keyless CI, §9 coverage. |
| [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) | Current status, the phase log (1–8), team division, house rules. |

---

### Where the code lives

All code is under [`agent-recommender/`](../agent-recommender/) (a stub README
there points back here). This `docs/` folder is the single source of truth for
documentation — each fact appears in exactly one file above; everything else
cross-links to it.
