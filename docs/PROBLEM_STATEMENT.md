# Problem Statement — Agent Recommender & Q&A Chatbot

> **This file is the behavior spec — the source of truth for *what* the system
> should do — and is kept stable.** For build *status* and the phase log, see
> [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md). For orientation, see
> [ONBOARDING.md](ONBOARDING.md). For *how* it's built, see
> [ARCHITECTURE.md](ARCHITECTURE.md) and [DATA_FLOW.md](DATA_FLOW.md).

## 1. Goal

Build a chatbot that helps users work with a catalog of AI agents. Given a
user's message, the chatbot does one of two things:

1. **Recommendation** — the user describes a need ("I want to turn manual test
   cases into automated UI scripts"), and the bot identifies which agent(s) best
   fit and explains why.
2. **Information lookup** — the user asks a question about an agent ("What's the
   autonomy level of the User Story Analyser?", "What does Test Data Provisioning
   output?"), and the bot answers, grounded in that agent's documentation.

The agent catalog is defined entirely by a set of Markdown (`.md`) files — one
per agent. The bot must answer only from these files and must not invent facts.

## 2. Tech Stack

- **Language:** Python 3.11+
- **Vector database:** ChromaDB (local/persistent). Stores embeddings **and**
  metadata; no separate relational database is required.
- **Approach:** Retrieval-Augmented Generation (RAG) for the information-lookup
  path; semantic search over agent summaries for the recommendation path.
- **LLM:** Configurable; default to a model the developer has API access to.
  Used for answer generation and recommendation explanations.
- **Embeddings:** Configurable; ChromaDB's built-in default embedding function is
  acceptable to start, and must be swappable without changing the architecture.

## 3. Input Data — the Agent Catalog

Each agent is a single `.md` file in an `agents/` directory, following one
normalized template: YAML **frontmatter** (the structured, filterable layer →
Chroma metadata) plus fixed **body sections** (the prose answered from at query
time). The section headers are identical across all files so the system can
reliably target one section.

> **The exact schema** — every frontmatter field and required `##` section, and
> what happens when a section is `TBD` — is documented in
> [AGENT_TEMPLATE.md](AGENT_TEMPLATE.md). It is the single source of truth for the
> file format.

There are currently **eight agents** in the catalog (`smarttdm-agenticdc`,
`user-story-analyser`, `test-data-provisioning`, `test-script-generator`,
`api-contract-validator`, `mobile-app-tester`, `security-scan-agent`,
`accessibility-auditor`). The catalog is expected to grow, so nothing is
hard-coded to a fixed agent count.

## 4. Functional Requirements

### 4.1 Indexing (offline, re-runnable)
- Scan `agents/`, parse each `.md` into frontmatter + body sections.
- Write two record types into ChromaDB: **agent-summary** (one per agent, coarse,
  for recommendation) and **section-chunk** (one per body section, fine, for info
  lookup). (Design rationale: [ARCHITECTURE.md](ARCHITECTURE.md).)
- Re-running the indexer must rebuild the store cleanly from the current files.

### 4.2 Intent detection
- Classify each message into `recommend`, `info`, or `clarify` (the last when the
  message is too vague to act on).

### 4.3 Recommendation path
- Semantic search over the agent-summary records; return the best-fitting agent
  with a short explanation of why.
- If several agents fit comparably, present a shortlist rather than forcing a pick.
- Support metadata filters where the query implies them (e.g. "which agents are
  fully autonomous" → filter on `autonomy_default`).

### 4.4 Information-lookup path (RAG)
- Identify which agent the question is about (by name/id, or by retrieval).
- Retrieve the most relevant section chunk(s), scoped with metadata filters.
- Generate an answer grounded strictly in the retrieved text.
- If the answer isn't present (e.g. Deployment fields are `TBD`), the bot must say
  it doesn't have that information rather than guessing.

### 4.5 Response behavior & edge cases
- **No match:** state that no agent clearly fits, and list the available agents.
- **Ambiguous:** ask one clarifying question, or show a shortlist.
- **Out of scope:** if the message isn't about the agents, say so politely.
- **Grounding:** never fabricate agent capabilities, inputs, outputs, or specs.

## 5. Build Order (incremental)

Build a thin end-to-end slice first, then expand; each phase runnable and testable
before the next: **(1)** loader → **(2)** indexer → **(3)** retriever → **(4)**
info path (RAG) → **(5)** recommendation path → **(6)** intent router → **(7)** CLI
→ **(8)** edge-case hardening + tests.

> This is the spec's recommended sequencing. The *actual* phase breakdown,
> status, and per-phase notes are tracked in
> [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md).

## 6. Non-Goals (out of scope)

- No authentication, multi-user state, or persistence beyond the Chroma store.
- The bot does not execute or deploy agents; it only answers about them.
- (A web/API front end was originally a non-goal for v1; a FastAPI backend
  (see [API_REFERENCE.md](API_REFERENCE.md)) and a Streamlit web UI
  ([frontend/README.md](../agent-recommender/frontend/README.md)) have since been
  added — but the core stays decoupled from any interface.)

## 7. Known Gaps & Assumptions

- The **Deployment** section (hardware/software) is currently `TBD` in the source
  files. The info path must handle "I don't have that information" gracefully until
  those fields are filled in.
- Triggers are not specified for some agents (empty `triggers` list); treat the
  absence as "not specified," not as "no triggers."
- The autonomy level for `smarttdm-agenticdc` was mapped to `L3` from a
  human-in-the-loop description; the structured field is the filter value and the
  prose is the authoritative explanation.

## 8. Acceptance Criteria

The build is complete when:

- Running the indexer populates ChromaDB from `agents/`.
- A recommendation query (e.g. "I need to automate UI tests from a live URL")
  returns the correct agent (`test-script-generator`) with an explanation.
- An info query (e.g. "What are the inputs to Test Data Provisioning?") returns an
  answer grounded in that file's `Inputs` section.
- A query for missing data (e.g. "What hardware does the User Story Analyser
  need?") returns an honest "not available" rather than a fabricated answer.
- A vague query triggers a single clarifying question.
- Adding a new `.md` file to `agents/` and re-indexing makes that agent
  discoverable with no code changes.

> How each criterion is verified in the test suite: [TESTING.md](TESTING.md).
