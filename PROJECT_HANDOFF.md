# Project Handoff & Onboarding — Agent Recommender & Q&A Chatbot

> Read this **together with `PROBLEM_STATEMENT.md`**. That file is the detailed
> spec (the source of truth for behavior). *This* file is the team-facing layer:
> current state, who owns what, the interface contracts that let us work in
> parallel, and each person's next step.

---

## 1. What we're building (in one paragraph)

A chatbot over a catalog of AI agents (currently four, all in the QA/testing
domain). Each agent is described by one Markdown file. The bot does two things:
**(a) recommendation** — the user describes a need and the bot says which agent
fits and why; **(b) information lookup** — the user asks about an agent ("what's
its autonomy level / inputs / outputs?") and the bot answers, grounded strictly
in that agent's doc. It must never invent facts.

## 2. Architecture & key decisions (already settled)

- **ChromaDB** is the datastore — it holds both embeddings (for semantic search)
  and metadata (for exact filters like `autonomy_default = L3`). No separate
  relational DB.
- **RAG** for the info-lookup path: retrieve the relevant section text, hand it
  to the LLM, generate a grounded answer.
- An **intent layer** sits in front and routes each message to `recommend`,
  `info`, or `clarify`.
- **Two retrieval granularities** stored in Chroma:
  - *agent-summary* records (one per agent) → used by the recommendation path.
  - *section-chunk* records (one per `##` section) → used by the info path.
- **CLI first.** Web/API later; keep core logic decoupled from the interface.

## 3. Current state (as of this handoff)

| Item | Status |
|------|--------|
| Agent catalog — 4 `.md` files normalized to one template (`agents/`) | ✅ Done |
| `PROBLEM_STATEMENT.md` (the spec) | ✅ Done |
| Repo folder structure scaffolded (stub files with docstrings) | ✅ Done |
| **Phase 1** — `models.py` + `loader.py` + `tests/test_loader.py` | 🔄 In progress (being done now) |
| Phase 2 — ChromaDB indexer | ⬜ Not started |
| Phase 3 — Recommendation path | ⬜ Not started |
| Phase 4 — Intent router + RAG info path | ⬜ Not started |
| Phase 5 — Orchestration, CLI, integration tests | ⬜ Not started |
| Deployment (hardware/software) fields in the docs | ⬜ Still `TBD` — being chased with manager |

## 4. Repo layout

```
agent-recommender/
├── agents/                 # 4 normalized .md agent docs (the input data)
├── src/
│   ├── models.py           # Agent data model            [Phase 1 — in progress]
│   ├── loader.py           # parse .md -> Agent           [Phase 1 — in progress]
│   ├── index.py            # build the ChromaDB store     [Phase 2]
│   ├── retriever.py        # query ChromaDB               [Phase 2]
│   ├── router.py           # intent detection             [Phase 4]
│   ├── chatbot.py          # orchestration                [Phase 5]
│   └── config.py           # paths, model names, top_k
├── tests/
├── app.py                  # CLI entry point              [Phase 5]
└── requirements.txt
```

## 5. Build order

```
Phase 1 (loader/model)  →  Phase 2 (indexer + retriever)  →  ┬─ Phase 3 (recommend)
                                                             └─ Phase 4 (router + RAG info)
                                                                        ↓
                                                             Phase 5 (orchestrate + CLI + QA)
```

Phases 3 and 4 run in parallel once Phase 2's retriever contract is agreed.

## 6. Team division (5 people)

1. **Data & Knowledge Base** — owns `agents/` + the `.md` template + the
   frontmatter schema (the contract everyone codes against); chasing the missing
   Deployment fields.
2. **Ingestion & Vector Store** — `models.py`, `loader.py`, `index.py`,
   `retriever.py`. The data-access layer everyone else consumes.
3. **Recommendation path** — the "which agent should I use?" feature end to end.
4. **Intent router + RAG info path** — `router.py` + the "answer a question about
   an agent" feature (the LLM/prompt-engineering core).
5. **Orchestration, Interface & QA** — `chatbot.py`, `app.py`, `config.py`, and
   the integration tests that check the acceptance criteria.

## 7. Interface contracts — AGREE THESE BEFORE CODING

These let everyone stub their dependencies and work in parallel. Treat the
signatures as fixed; change them only by team agreement.

**Agent** (produced by Phase 1, consumed by everyone):
```
Agent:
  agent_id: str
  name: str
  domain: str
  tags: list[str]
  autonomy_default: str
  autonomy_supported: list[str]
  triggers: list[str]
  sections: dict[str, str]          # "Overview" -> raw markdown text
  source_path: str
  get_section(name: str) -> str | None
  summary_text() -> str
```

**Retriever** (Phase 2 provides; Phases 3 & 4 consume):
```
search_agents(query: str, k: int = 3, where: dict | None = None) -> list[Hit]
search_sections(query: str, k: int = 5, where: dict | None = None) -> list[Hit]
# `where` is a Chroma metadata filter, e.g. {"autonomy_default": "L3"}
# Hit = { agent_id: str, name: str, section: str | None, text: str,
#         score: float, metadata: dict }
```

**Recommendation path** (Phase 3 provides; Phase 5 consumes):
```
recommend(query: str) -> { agents: list[Hit], explanation: str, ambiguous: bool }
```

**Intent router** (Phase 4 provides; Phase 5 consumes):
```
detect_intent(query: str) -> "recommend" | "info" | "clarify"
```

**Info / RAG path** (Phase 4 provides; Phase 5 consumes):
```
answer_question(query: str) -> { answer: str, sources: list[Hit], grounded: bool }
# grounded=False (and an honest "I don't have that") when the answer isn't in the
# retrieved text — e.g. Deployment fields are still TBD.
```

**Chatbot** (Phase 5 provides):
```
handle(message: str) -> str   # detect_intent -> route -> format reply
```

## 8. Your next step — ready-to-run Claude Code prompts

Each prompt is scoped to one module. The rule: **implement only your module;
stub your dependencies against the contracts in section 7; run your own tests.**
Always start the session by telling Claude Code to read `PROBLEM_STATEMENT.md`
and this handoff file.

### Phase 2 — Ingestion & Vector Store
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Phase 1 (models.py, loader.py)
is done. Implement Phase 2 ONLY: src/index.py and src/retriever.py.
- index.py: use load_agents() to read agents/, then build a persistent ChromaDB
  store with TWO record sets — one agent-summary record per agent (embed
  summary_text()) and one section-chunk record per section. Store agent_id, name,
  section, and the frontmatter fields as scalar metadata (flatten list fields like
  tags/triggers/autonomy_supported into Chroma-compatible values). Make re-running
  rebuild the store cleanly.
- retriever.py: implement search_agents() and search_sections() exactly as in
  section 7 of PROJECT_HANDOFF.md, including the `where` metadata filter.
- Add chromadb to requirements.txt. Use Chroma's default embedding function for now.
Write tests that index the real agents/ files and assert that a query returns the
expected agent. Do NOT implement the router, recommendation, chatbot, or CLI.
After implementing, run the tests and show results.
```

### Phase 3 — Recommendation path
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement the recommendation
path ONLY, exposing recommend(query) exactly as in section 7. Use
search_agents() from retriever.py (stub it against the section-7 contract if it's
not merged yet). Rank the best-fitting agent(s), produce a short explanation of
why, support metadata-filtered queries (e.g. "fully autonomous agents" ->
where={"autonomy_default": "L4"}), and handle the ambiguous case with a shortlist.
Do NOT implement the info path, router, or CLI. Write tests for: a clear single
match, an ambiguous case, and a metadata-filtered query. Run the tests and show
results.
```

### Phase 4 — Intent router + RAG info path
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement router.py and the
RAG info path ONLY. detect_intent(query) returns "recommend" | "info" | "clarify"
per section 7. answer_question(query) identifies the target agent, uses
search_sections() (stub against the section-7 contract if not merged) to retrieve
the right section(s), then has the LLM answer GROUNDED STRICTLY in retrieved text;
when the info isn't present (e.g. Deployment is TBD) return grounded=False with an
honest "I don't have that information." Do NOT implement recommendation or CLI.
Write tests for: an inputs/outputs question, a missing-data question (must not
hallucinate), and intent classification on a few sample messages. Run and show
results.
```

### Phase 5 — Orchestration, CLI & QA
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Implement chatbot.py, app.py,
and config.py ONLY. handle(message) calls detect_intent() then routes to
recommend() or answer_question() or asks one clarifying question, then formats the
reply. Stub the path functions against the section-7 contracts until they're
merged. app.py is a simple REPL. Then write integration tests covering the
acceptance criteria in PROBLEM_STATEMENT.md section 9 (correct recommendation,
grounded info answer, honest "not available", vague->clarify, and that adding a
new .md + re-index makes it discoverable). Run and show results.
```

### Person 1 — Data & schema (ongoing)
```
Read PROBLEM_STATEMENT.md and PROJECT_HANDOFF.md. Audit the four files in agents/
against the template in PROBLEM_STATEMENT.md section 3: confirm identical section
headers, valid frontmatter, and consistent autonomy values. Then fill the
Deployment (Hardware/Software) sections once the manager provides them, keeping
the same template. Do not change any code.
```

## 9. Working agreements

- `PROBLEM_STATEMENT.md` is the source of truth for behavior; this file is for
  state, ownership, and contracts.
- One phase per Claude Code session; don't edit another person's module.
- Stub dependencies against the section-7 contracts so no one is blocked.
- Everyone unit-tests their own module; Person 5 owns end-to-end tests.
- If a contract needs to change, raise it with the team — don't change it locally.
