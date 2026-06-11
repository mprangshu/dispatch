# Agent Template

The exact schema every catalog file in
[agent-recommender/agents/](../agent-recommender/agents/) must follow. The catalog
is defined **entirely** by these `.md` files — to add or change an agent you edit
files here and re-index; **no code changes** (PROBLEM_STATEMENT.md §3 & §9).

Each agent is **one `.md` file**. The filename stem should match `agent_id`
(e.g. `test-data-provisioning.md`).

---

## The template

```markdown
---
agent_id: <slug>                       # kebab-case, unique; matches the filename
name: <Display Name>                   # human-readable
domain: <e.g. testing>
tags: [<keyword>, <keyword>, ...]      # YAML list; powers search + the /agents list
autonomy_default: <L1|L2|L3|L4>        # the filterable autonomy level
autonomy_supported: [<L1>, <L2>, ...]  # YAML list
triggers: [<manual|api|webhook>]       # YAML list; may be empty []
---

## Overview
## Autonomy Level
## Inputs
## Outputs
## Triggers
## Deployment        # Hardware / Software — may currently be "TBD"
## Limitations
```

Two layers, both used by the system:

- **Frontmatter** (between the `---` fences) = the structured, filterable layer →
  becomes ChromaDB **metadata**.
- **Body sections** (`## Heading`) = the prose answered from at query time. The
  headers are **identical across all files**, which is what lets the info path
  reliably target a single section.

---

## Frontmatter fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `agent_id` | string (slug) | yes | Unique. Defaults to the filename stem if omitted, but always set it explicitly. |
| `name` | string | yes | Display name shown to users and in `/agents`. |
| `domain` | string | yes | e.g. `testing`. |
| `tags` | list[string] | yes | Distinctive keywords. Feed both the recommendation embedding and `/agents`. Pick terms a user might actually describe their need with. |
| `autonomy_default` | `L1`–`L4` | yes | The single value used for metadata **filtering** (e.g. "fully autonomous" → `L4`). |
| `autonomy_supported` | list of `L1`–`L4` | yes | All levels the agent can run at. |
| `triggers` | list | no | `manual` / `api` / `webhook`. **Empty `[]` is valid** and means "not specified" — not "no triggers". |

> Frontmatter is parsed as YAML. Lists must be valid YAML lists (`[a, b]` or a
> block list). The loader coerces a lone scalar into a one-item list and a
> missing/`None` value into `[]`, so partially-filled files still load.

## Body sections

All seven headers should be present (identical spelling/casing) so retrieval can
target them. Section bodies are kept as **raw markdown** — tables are preserved
verbatim and answered from as-is (not parsed into structured data).

| Section | Maps to (info path) | Typical content |
|---------|---------------------|-----------------|
| `## Overview` | `Overview` | What the agent does. Also feeds the recommendation summary. |
| `## Autonomy Level` | `Autonomy Level` | Prose + a level table. The prose is authoritative; the frontmatter value is the filter. |
| `## Inputs` | `Inputs` | What it needs (often a table). |
| `## Outputs` | `Outputs` | What it produces. |
| `## Triggers` | `Triggers` | How it's invoked, or "Not specified in source." |
| `## Deployment` | `Deployment` | Hardware / Software. **May be `TBD`** — see below. |
| `## Limitations` | `Limitations` | Constraints, or "Not specified in source." |

The info router maps question words to these headers (e.g. "inputs" → `Inputs`,
"hardware/software/requirements" → `Deployment`, "autonomy" → `Autonomy Level`).

---

## What happens when a section is `TBD` / not specified

This is a first-class case (PROBLEM_STATEMENT.md §4.4 & §8), not an error:

- A section whose body is `TBD`, "Not specified in source", "Not available", or
  effectively empty is detected by `info._looks_missing` as having **no real
  content**.
- A question about that section returns `grounded=False` with an honest **"I don't
  have that information…"** — and the **LLM is never consulted**, so it cannot
  invent a value.
- The current known gap: every agent's `## Deployment` is `**Hardware:** TBD` /
  `**Software:** TBD`. Filling these in (same template) is the only open data item;
  it requires no code change — just edit the file and re-index.

So you can ship an agent with incomplete sections: the bot will simply say it
doesn't have that detail until you fill it in.

---

## Adding a new agent — checklist

1. Create `agents/<agent_id>.md` following the template above.
2. Use valid YAML frontmatter (run a quick `pytest tests/test_loader.py` — the
   loader tests run against the real catalog and will flag a malformed file).
3. Keep the seven section headers spelled exactly as shown.
4. Re-index: `python app.py index`.
5. Verify discoverability: ask the chatbot a question that should match it, or
   `GET /agents` to confirm it's listed.

No code changes are needed at any step — a test
(`test_new_agent_is_discoverable_after_reindex`) locks in exactly this behavior.

## Worked example

See [test-data-provisioning.md](../agent-recommender/agents/test-data-provisioning.md)
for a complete, valid file: note `triggers: []` (empty = not specified) and the
`## Deployment` section left as `TBD`.
