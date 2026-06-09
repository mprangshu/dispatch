# Problem Statement — Agent Recommender & Q&A Chatbot

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
  Used for intent detection, answer generation, and recommendation explanations.
- **Embeddings:** Configurable; ChromaDB's built-in default embedding function is
  acceptable to start. The embedding model must be swappable without changing
  the rest of the architecture.

## 3. Input Data — the Agent Catalog

Each agent is a single `.md` file placed in an `agents/` directory. All files
follow one normalized template:

```markdown
---
agent_id: <slug>
name: <Display Name>
domain: <e.g. testing>
tags: [<keyword>, <keyword>]
autonomy_default: <L1|L2|L3|L4>
autonomy_supported: [<L1>, ...]
triggers: [<manual|api|webhook>]   # may be empty
---

## Overview
## Autonomy Level
## Inputs
## Outputs
## Triggers
## Deployment        # Hardware / Software — may currently be "TBD"
## Limitations
```

- **Frontmatter** is the structured, filterable layer (used as Chroma metadata):
  `agent_id`, `name`, `domain`, `tags`, `autonomy_default`, `autonomy_supported`,
  `triggers`.
- **Body sections** carry the prose answered from at query time. Section headers
  are identical across all files, so the system can reliably target one section.

There are currently **four agents** in the catalog:
`smarttdm-agenticdc`, `user-story-analyser`, `test-data-provisioning`,
`test-script-generator`. The catalog is expected to grow, so nothing should be
hard-coded to four agents.

## 4. Functional Requirements

### 4.1 Indexing (offline, re-runnable)
- Scan the `agents/` directory and load every `.md` file.
- Parse each file into frontmatter (metadata) and body sections.
- Write two kinds of records into ChromaDB:
  - **Agent-summary records** — one per agent (coarse), used for the
    recommendation path. Embed a concise summary (name + overview + tags).
  - **Section-chunk records** — one per body section (fine), used for the
    info-lookup path. Each chunk stores `agent_id`, `name`, `section` (e.g.
    "Autonomy Level"), and the frontmatter fields as metadata.
- Re-running the indexer must rebuild the store cleanly from the current files.

### 4.2 Intent detection
- Classify each incoming message into one of: `recommend`, `info`, or `clarify`.
- `clarify` is used when the message is too vague to act on.

### 4.3 Recommendation path
- Run semantic search over the agent-summary records.
- Return the best-fitting agent with a short explanation of why it fits.
- If multiple agents fit comparably, present a short shortlist rather than
  forcing a single pick.
- Support metadata filters where the query implies them (e.g. "which agents are
  fully autonomous" → filter on `autonomy_default`).

### 4.4 Information-lookup path (RAG)
- Identify which agent the question is about (by name/agent_id, or by retrieval).
- Retrieve the most relevant section chunk(s) for that agent, using metadata
  filters to scope to the right agent and, where possible, the right section.
- Pass the retrieved chunks plus the question to the LLM and generate an answer
  grounded strictly in the retrieved text.
- If the answer is not present in the retrieved content (e.g. Deployment fields
  are "TBD"), the bot must say it doesn't have that information rather than
  guessing.

### 4.5 Response behavior & edge cases
- **No match:** state that no agent clearly fits, and list the available agents.
- **Ambiguous:** ask one clarifying question, or show a shortlist.
- **Out of scope:** if the message isn't about the agents at all, say so politely.
- **Grounding:** never fabricate agent capabilities, inputs, outputs, or specs.

## 5. Suggested Project Structure

```
agent-recommender/
├── agents/                 # the .md catalog (input data)
├── src/
│   ├── models.py           # Agent data model
│   ├── loader.py           # parse .md -> frontmatter + sections
│   ├── index.py            # build the ChromaDB store from the catalog
│   ├── retriever.py        # query ChromaDB (semantic + metadata filters)
│   ├── router.py           # intent detection
│   ├── chatbot.py          # orchestration: intent -> path -> grounded reply
│   └── config.py           # paths, model names, top_k, thresholds
├── tests/
├── app.py                  # CLI entry point
└── requirements.txt
```

## 6. Build Order (incremental)

Build a thin end-to-end slice first, then expand. Each phase should be runnable
and testable before moving on.

1. **Loader** — parse a `.md` file into a structured object (metadata + sections).
2. **Indexer** — build the ChromaDB store (both record types) from `agents/`.
3. **Retriever** — query the store with semantic search + metadata filters.
4. **Info path (RAG)** — retrieve section chunks → LLM → grounded answer. This is
   the first full vertical slice; validate it before continuing.
5. **Recommendation path** — semantic search over agent summaries + explanation.
6. **Intent router** — classify and route between the two paths and `clarify`.
7. **CLI interface** — wire it together in `app.py`.
8. **Edge-case hardening + tests** — no-match, ambiguous, out-of-scope, grounding.

## 7. Non-Goals (out of scope)

- No web/API front end in the first version (CLI only). It may be added later;
  keep the core logic decoupled from the interface so this is easy.
- No authentication, multi-user state, or persistence beyond the Chroma store.
- The bot does not execute or deploy agents; it only answers about them.

## 8. Known Gaps & Assumptions

- The **Deployment** section (hardware/software requirements) is currently `TBD`
  in the source files. The info path must handle "I don't have that information"
  gracefully until those fields are filled in.
- Triggers are not specified for some agents (empty `triggers` list); treat the
  absence as "not specified," not as "no triggers."
- The autonomy level for `smarttdm-agenticdc` was mapped to `L3` from a
  human-in-the-loop description; treat the structured field as the filter value
  and the prose as the authoritative explanation.

## 9. Acceptance Criteria

The build is complete when:

- Running the indexer populates ChromaDB from the `agents/` directory.
- A recommendation query (e.g. "I need to automate UI tests from a live URL")
  returns the correct agent (`test-script-generator`) with an explanation.
- An info query (e.g. "What are the inputs to Test Data Provisioning?") returns
  an answer grounded in that file's `Inputs` section.
- A query for missing data (e.g. "What hardware does the User Story Analyser
  need?") returns an honest "not available" rather than a fabricated answer.
- A vague query triggers a single clarifying question.
- Adding a new `.md` file to `agents/` and re-indexing makes that agent
  discoverable with no code changes.
```
