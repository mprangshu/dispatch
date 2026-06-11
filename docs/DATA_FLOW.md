# Data Flow

How a single user message travels through the system, end to end. Follow the
numbered steps; the diagram and worked examples at the bottom tie it together.

The entry point for every message is `chatbot.handle(message, use_llm=True)`
([src/chatbot.py](../agent-recommender/src/chatbot.py)).

---

## The pipeline at a glance

```
            user message
                 │
                 ▼
        ┌───────────────────┐
        │ 1. empty? ───────────────► clarify reply (no routing)
        └───────────────────┘
                 │ non-empty
                 ▼
        ┌───────────────────┐
        │ 2. detect_intent  │  (deterministic rules — no LLM)
        └───────────────────┘
           │        │        │
     recommend     info    clarify
           │        │        │
           ▼        ▼        ▼
   3a. recommend() 3b. answer_question()   3c. ask one
       (semantic       (RAG over               clarifying
        search over     section chunks)         question +
        summaries)          │                   list agents
           │                ▼
           │         ┌───────────────┐
           │         │ GROUNDING GATE│ ──► TBD/empty? honest
           │         └───────────────┘     "I don't have that"
           │                │ has content
           ▼                ▼
   4. LLM explanation   4. LLM answer (grounded)
      OR fallback          OR verbatim fallback
           │                │
           ▼                ▼
        ┌───────────────────────────┐
        │ 5. format ONE reply string│
        └───────────────────────────┘
                 │
                 ▼
        CLI (app.py)  /  HTTP (api.py → POST /chat)  /  Streamlit UI (frontend/)
```

---

## Step 1 — Receive & guard

`handle` strips the message. If it's empty, it short-circuits straight to a
**clarify** reply (no routing, no retrieval). Otherwise it continues.

## Step 2 — Intent detection (deterministic, no LLM)

`router.detect_intent(text)` classifies into one of three labels:

| Intent | Meaning | Trigger examples |
|--------|---------|------------------|
| `recommend` | User describes a need / wants a fitting agent. | "I need to automate UI tests", "which agent is fully autonomous" |
| `info` | User asks about a specific agent's details. | "what are the inputs to Test Data Provisioning?" |
| `clarify` | Too vague to act on. | "hi", "help" |

How the rules decide ([src/router.py](../agent-recommender/src/router.py)):

1. **Names an agent?** `find_agent` matches catalog-derived name variants → `info`.
   (Agent names are read live from `agents/`, never hard-coded.)
2. Otherwise weigh two regex signals: a *recommend* phrasing vs. an *info attribute
   question*. One without the other wins; both present → `recommend` (a
   cross-catalog ask like "which agent has the highest autonomy").
3. No strong signal: fewer than 3 words → `clarify`; a task verb present →
   `recommend`; else `clarify`.

> **Important:** `handle` always uses the deterministic rules for routing — it
> never spends an LLM call on intent. `use_llm` is threaded only into the *answer
> generation* in steps 3–4.

## Step 3a — Recommendation path

`recommender.recommend(query)` ([src/recommender.py](../agent-recommender/src/recommender.py)):

1. **Implied filter.** `detect_filter` turns "fully autonomous" → `where={"autonomy_default":"L4"}`,
   or an explicit `L1`–`L4` directly. Else no filter.
2. **Semantic search** over `agent_summaries` via `search_agents(query, k=RECOMMEND_TOP_K, where=...)`.
3. **Decide**, using thresholds from `config.py`:
   - No hits, or (unfiltered) top score `< NO_MATCH_SCORE (0.15)` → **no match**:
     empty list + honest message. (A filter is treated as strong intent, so the
     score floor is skipped when one was applied.)
   - Runner-up within `AMBIGUITY_DELTA (0.07)` of the top → **ambiguous**: return a
     shortlist, `ambiguous=True`.
   - Otherwise → **single** best agent.
4. Returns `{ agents: list[Hit], explanation: str, ambiguous: bool }`.

## Step 3b — Info path (RAG)

`info.answer_question(query)` ([src/info.py](../agent-recommender/src/info.py)):

1. **Find the agent** (`find_agent`) and **find the section** (`detect_section`
   maps "inputs"→`Inputs`, "hardware"→`Deployment`, etc.).
2. **Build a `where` filter** from agent and/or section.
3. **Retrieve** with `search_sections(query, k=INFO_TOP_K=5, where=...)`. If a tight
   section filter returns nothing, **widen**: agent-only, then whole catalog.
4. **Pick the top relevant section** and recover its body text.

## The grounding gate

Before generating anything, `info.py` checks the chosen section body with
`_looks_missing`. If it's `TBD`, "not specified", or effectively empty:

> return `{ answer: "I don't have that information…", sources: [top], grounded: False }`

**The LLM is never called in this case**, so it cannot invent a value. This is the
core safety property (PROBLEM_STATEMENT.md §4.4 and §8). A second guard: if the LLM
*is* called and replies `INSUFFICIENT_CONTEXT`, that also maps to `grounded=False`.

## Step 4 — Generate (LLM with deterministic fallback)

Both paths now produce prose, governed by `use_llm` and `llm.generate`'s result
([src/llm.py](../agent-recommender/src/llm.py)):

| Path | LLM available | LLM unavailable (`generate` → `None`) |
|------|---------------|----------------------------------------|
| recommend | LLM writes a grounded "why it fits", starting with the agent name | Template: "I'd recommend **<name>**." + overview snippet + tags |
| info | LLM answers using *only* the retrieved excerpts | Quotes the section verbatim: "From the <name> documentation (<section>): …" |

The LLM is always told to use only the supplied text and never invent
capabilities. Temperature is low (0.5) for stable output.

## Step 5 — Format one reply

`chatbot.py` turns the path result into a single string:

- **recommend, matched** → the explanation as-is.
- **recommend, no match** → explanation **+ a bulleted list of available agents**
  (read live from the catalog).
- **info, grounded** → the answer **+ a `_Source: <name> — <section>_` line**.
- **info, ungrounded** → the honest "I don't have that" passes straight through,
  **with no source line**.
- **clarify** (or empty input) → one clarifying question + what the bot can do +
  the available agents.

## Step 6 — Delivery

The same string is returned to whichever interface called `handle`:

- **CLI** (`app.py`) prints it in the REPL.
- **API** (`api.py`) wraps it as `POST /chat` → `{ "reply": "..." }`.
- **UI** (`frontend/`, Streamlit) renders it as a chat bubble, calling `/chat` over HTTP.

Because all three call the identical `handle`, the answer is the same everywhere.

---

## Worked examples

### A. Recommendation (clear match)

```
"I need to automate UI tests from a live URL"
 → detect_intent: recommend
 → detect_filter: none
 → search_agents → top hit: test-script-generator (strong, clear gap)
 → single match → LLM/fallback explanation
 → reply: "I'd recommend **Test Script Generator Agent**. …"
```

### B. Info (grounded)

```
"What are the inputs to Test Data Provisioning?"
 → detect_intent: info  (agent named)
 → find_agent: test-data-provisioning ; detect_section: Inputs
 → where = {$and:[{agent_id:...},{section:"Inputs"}]}
 → search_sections → Inputs chunk (has a real table)
 → grounding gate: content present → grounded
 → reply: "<answer about User Story ID, …>\n\n_Source: Test Data Provisioning — Inputs_"
```

### C. Missing data (honest, the gate fires)

```
"What hardware does the User Story Analyser need?"
 → detect_intent: info
 → find_agent: user-story-analyser ; detect_section: Deployment
 → search_sections → Deployment chunk = "**Hardware:** TBD  **Software:** TBD"
 → grounding gate: _looks_missing → grounded=False, LLM NOT called
 → reply: "I don't have that information. The User Story Analyser documentation
           doesn't specify its deployment — it's currently marked TBD / not specified."
   (no source line)
```

### D. Vague (clarify)

```
"hi"
 → detect_intent: clarify  (fewer than 3 words, no signal)
 → reply: "I'm not sure what you need yet. You can describe a task … or ask about
           a specific agent …\n\nAvailable agents:\n- …"
```
