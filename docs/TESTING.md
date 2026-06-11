# Testing

How the test suite is structured, the patterns that keep it fast and
network-free, and what proves the acceptance criteria.

- **Runner:** `pytest`. Run the whole suite from `agent-recommender/`:
  ```bash
  pytest
  ```
- **Status:** 95 tests passing.
- **No API key required.** Everything runs offline (see the patterns below).

---

## Test layout (one file per module + integration)

| File | Covers | Notes |
|------|--------|-------|
| [tests/test_loader.py](../agent-recommender/tests/test_loader.py) | Phase 1 — `loader.py` + `models.py` | Runs against the **real** `agents/` files, so it doubles as a catalog sanity check. |
| [tests/test_indexer.py](../agent-recommender/tests/test_indexer.py) | Phase 2 — `index.py` + `retriever.py` | Builds a throwaway Chroma store and queries it. |
| [tests/test_recommender.py](../agent-recommender/tests/test_recommender.py) | Phase 3 — `recommender.py` | Clear match, ambiguous shortlist, metadata-filtered query, no-match. |
| [tests/test_router.py](../agent-recommender/tests/test_router.py) | Phase 4 — `router.py` | Intent classification across sample messages. |
| [tests/test_info.py](../agent-recommender/tests/test_info.py) | Phase 4 — `info.py` | Inputs/outputs question, missing-data (no hallucination), section detection. |
| [tests/test_chatbot.py](../agent-recommender/tests/test_chatbot.py) | Phase 5 — `chatbot.py` (E2E) | The §9 acceptance criteria, end to end. |
| [tests/test_llm.py](../agent-recommender/tests/test_llm.py) | Phase 6 — LLM guardrails | **Fully mocked** — proves the grounding gate holds with the LLM "on". |
| [tests/test_api.py](../agent-recommender/tests/test_api.py) | Phase 7 — `api.py` | FastAPI endpoints via `TestClient`. |
| [frontend/tests/test_ui.py](../agent-recommender/frontend/tests/test_ui.py) | Phase 8 — `frontend/` UI | Mocks the HTTP layer (`requests.get`/`post`) — no live server or Streamlit session needed. |

---

## The two injection patterns (why it runs offline)

Every test avoids the network in one of two ways. Understand these and the suite
makes sense.

### 1. `use_llm=False` — skip the LLM, take the deterministic path

The paths and `handle` all accept `use_llm`. With `use_llm=False`, no LLM call is
made and the **grounded fallback** runs instead (templated explanation / verbatim
section). The facts and the grounding verdict are identical to the LLM-on path —
only the prose differs — so tests assert on facts deterministically:

```python
reply = handle("I need to automate UI tests from a live URL", use_llm=False)
assert "Test Script Generator" in reply
```

### 2. `search_fn=` — inject a stub retriever

`recommend` and `answer_question` take a `search_fn` (defaulting to the real
retriever). Tests pass a lambda returning hand-built `Hit`s, so they exercise the
path logic with **no Chroma store at all**:

```python
res = info.answer_question(
    "What are the inputs to Test Data Provisioning?",
    use_llm=True,                      # LLM branch...
    search_fn=lambda *a, **k: [hit],   # ...but retrieval is stubbed
)
```

Where tests *do* want the real store, they build it into a **temp dir** and point
`config.CHROMA_PATH` at it (restoring afterward) — e.g. the `built_store` fixture
in `test_chatbot.py` and `test_api.py`. So even "real index" tests don't touch your
working `.chroma/`.

### Mocking the LLM (Phase 6)

`test_llm.py` monkeypatches `llm.generate` (and the per-module `generate` imports,
e.g. `info.generate`) to return canned text or `None`. This drives the live LLM
*branches* with **no key, no network, no quota** — so CI behaves exactly like
local. The critical test feeds a fabricated hardware spec into a `TBD` section and
asserts none of it leaks:

```python
# grounding gate short-circuits before the LLM, so the fabrication can't surface
assert res["grounded"] is False
for invented in ("a100", "gpu", "ram", "gb", "cpu", "cores"):
    assert invented not in res["answer"].lower()
```

---

## Running CI without a key

Nothing special is required:

- No `GEMINI_API_KEY` → `llm.available()` is `False`, `llm.generate()` returns
  `None`, paths fall back deterministically. All 95 tests pass.
- `test_api.py::test_health_reports_ok_and_llm_flag` asserts `llm_available`
  **matches** `llm.available()` rather than a fixed value, so it's correct whether
  or not a key is present.
- The first run downloads the local embedding model (~tens of MB, ~1 min); cached
  after that.

```bash
pip install -r requirements.txt
pytest            # green, offline, no key
```

---

## What `test_chatbot.py` proves (acceptance criteria, §9)

Each criterion in PROBLEM_STATEMENT.md §9 has a test:

| Acceptance criterion | Test |
|----------------------|------|
| Recommendation returns the correct agent | `test_recommendation_returns_correct_agent` → expects `test-script-generator`. |
| Info answer grounded in the right section | `test_info_answer_is_grounded_in_the_right_section` → "User Story ID" from the Inputs table + source attribution. |
| Missing data → honest, never fabricated | `test_missing_data_is_honest_not_fabricated` → "don't have", and asserts no `gpu/cpu/ram/...` leaked. |
| Vague → one clarifying question | `test_vague_message_triggers_clarification`. |
| New `.md` + re-index → discoverable, no code change | `test_new_agent_is_discoverable_after_reindex` → adds a 5th agent, re-indexes, finds it via search. |

Plus stubbed routing/formatting edges (monkeypatching `chatbot.detect_intent` /
`chatbot.recommend` / `chatbot.answer_question`): no-match lists the catalog,
grounded info gets a `Source:` line, ungrounded info gets **no** source line, and
an ambiguous result surfaces the shortlist.

## Manual LLM verification (not part of `pytest`)

[scripts/verify_llm.py](../agent-recommender/scripts/verify_llm.py) runs three
queries with the LLM **on vs. off** and prints them side by side. The check: facts
and the grounding verdict must be **identical** in both columns (especially the
`TBD` "I don't have that"); only the wording should get richer with a key. Needs
the store built; with no key, the on-column simply matches off.

```bash
python app.py index
python scripts/verify_llm.py
```

---

## Adding tests — conventions

- One `test_<module>.py` per module; integration/E2E lives in `test_chatbot.py`.
- Default to `use_llm=False` and/or `search_fn=` stubs so tests stay offline and
  deterministic.
- If you need the real store, build into a `tmp_path` and restore
  `config.CHROMA_PATH` — never write to the repo's `.chroma/`.
- Assert on **facts and grounding**, not on exact LLM prose (which varies).
