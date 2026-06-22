# Test Suite Reference

A complete, test-by-test reference for the **Agent Recommender & Q&A Chatbot**.
For each test it records *what it checks*, *which function/module is under test*,
*why it matters*, and *how it stays offline*. This is the detailed companion to
[TESTING.md](TESTING.md) (which owns the high-level patterns and the acceptance-
criteria mapping).

> **Scope note.** The original docs mention "101 passing". The catalog and the
> code have grown since (a real-catalog refresh, the *not-in-catalog* grounding
> gate, and a comprehensive edge-case suite), so the suite is now **160 tests**.
> Everything still runs **offline with no API key**.

---

## 1. How to run

```bash
# from agent-recommender/, venv active
pytest                       # whole suite
pytest tests/test_info.py    # one file
pytest -k "not_in_catalog"   # by keyword
pytest -q tests/test_edge_cases.py -v   # verbose, one group
```

- **No `GEMINI_API_KEY` required.** Every test takes a deterministic path
  (`use_llm=False`), injects a stub retriever (`search_fn=`), monkeypatches
  `llm.generate`, or mocks the HTTP layer.
- **The repo's `.chroma/` and `agents/` are never written to.** Tests that need a
  real index build into a `tmp_path` and restore `config.CHROMA_PATH` /
  `config.AGENTS_DIR` afterward.
- **First run is slow** (~minutes): ChromaDB downloads the local embedding model
  (`all-MiniLM-L6-v2`, ~tens of MB) once, and several suites build a real store.

---

## 2. Totals at a glance

| Test file | Tests | Layer / module under test | Needs a real store? |
|-----------|------:|---------------------------|---------------------|
| `tests/test_loader.py` | 10 | `loader.py` + `models.py` (Phase 1) | No (real files, no embeddings) |
| `tests/test_indexer.py` | 7 | `index.py` + `retriever.py` (Phase 2) | **Yes** (temp) |
| `tests/test_recommender.py` | 10 | `recommender.py` (Phase 3) | Partly (clear/filter tests) |
| `tests/test_router.py` | 23 | `router.py` (Phase 4) | No (catalog file read only) |
| `tests/test_info.py` | 18 | `info.py` (Phase 4) | No (stubbed retriever) |
| `tests/test_chatbot.py` | 10 | `chatbot.py` (Phase 5, E2E) | Partly |
| `tests/test_llm.py` | 10 | LLM guardrails (Phase 6) | No (mocked LLM) |
| `tests/test_api.py` | 6 | `api.py` (Phase 7) | Partly |
| `tests/test_store.py` | 4 | `store.py` caching + invalidation | **Yes** (temp) |
| `tests/test_logging.py` | 3 | `logger.py` tracing | Partly |
| `tests/test_not_in_catalog.py` | 21 | not-in-catalog grounding gate (cross-module) | No (stubs) |
| `tests/test_edge_cases.py` | 27 | system boundaries (cross-module) | Partly (temp) |
| `frontend/tests/test_ui.py` | 11 | `frontend/api_client.py` (Phase 8) | No (mocked `requests`) |
| **Total** | **160** | | |

---

## 3. Testing techniques (why it all runs offline)

Five injection/mocking patterns recur. Knowing them makes every test legible.

| Pattern | Where | What it does |
|---------|-------|--------------|
| **`use_llm=False`** | `handle`, `recommend`, `answer_question` | Skips the LLM and takes the deterministic, grounded fallback. Facts/grounding are identical to the LLM-on path, so assertions on *facts* are stable. |
| **`search_fn=` stub** | `recommend`, `answer_question` | Injects a lambda returning hand-built `Hit`s, so path logic runs with **no Chroma store at all**. |
| **Temp real store** | `index.build_index(chroma_path=tmp)` + restore `config.CHROMA_PATH` | Builds the *real* catalog into a throwaway dir for true end-to-end retrieval, without touching the repo's `.chroma/`. |
| **Monkeypatched `llm.generate`** | `test_llm.py`, `test_logging.py` | Drives the *live* LLM branches with canned text / `None` — no key, no network, no quota. |
| **Mocked `requests` / `TestClient`** | `test_ui.py`, `test_api.py` | Exercises the HTTP client and FastAPI app with no live server. |

### Shared fixtures

| Fixture | Files | Purpose |
|---------|-------|---------|
| `built_store` (module-scoped) | `test_indexer`, `test_recommender`, `test_chatbot`, `test_api`, `test_logging` | Indexes the real catalog into a temp Chroma path, points `config.CHROMA_PATH` at it, restores after. |
| `temp_store` (function-scoped) | `test_store` | Points `config.CHROMA_PATH` at a temp dir **and** resets the `store.py` singletons via `monkeypatch`. |
| `real_store` (module-scoped) | `test_edge_cases` | Same as `built_store` (separate temp dir). |
| `build_catalog(...)` (contextmanager) | `test_edge_cases` | Writes a synthetic catalog (empty / one-agent / malformed) to a temp dir, overrides `AGENTS_DIR` + `CHROMA_PATH`, indexes, clears caches, restores. |
| `api_client` | `test_edge_cases` | A `TestClient(app)` for the FastAPI app. |
| `_clear_caches()` | `test_edge_cases` | Clears `router._agent_terms`, `chatbot.available_agent_names`, `recommender._catalog_vocab` so a swapped catalog is seen immediately. |

---

## 4. `tests/test_loader.py` — Phase 1: parsing (10 tests)

**Under test:** `src/loader.py` (`load_agent`, `load_agents`) and `src/models.py`
(`Agent`, `get_section`, `summary_text`). Runs against the **real** `agents/`
files, so it doubles as a catalog sanity check.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_all_agents_load` | A known set of `agent_id`s is present and ids are unique. | Confirms the whole catalog parses and there are no duplicate ids. |
| `test_frontmatter_lists_and_scalars_parsed` | `test-data-provisioning` has the right `autonomy_default`, `autonomy_supported` (list stays a list), `domain`, `tags`. | The frontmatter→`Agent` mapping is the contract everyone codes against. |
| `test_empty_triggers_is_empty_list_not_error` | `triggers: []` parses to `[]`, not an error. | "Absence = not specified," a first-class case (PROBLEM_STATEMENT §8). Uses a synthetic file. |
| `test_populated_triggers_parsed` | `user-story-analyser` triggers = `[manual, api, webhook]`. | Lists survive parsing intact. |
| `test_get_section_returns_text` | `get_section("Inputs")` returns non-empty raw markdown (tables preserved, `\|` present). | Section bodies are answered from verbatim; must not be mangled. |
| `test_get_section_is_case_insensitive` | `get_section("inputs") == get_section("Inputs")`. | The info path looks sections up case-insensitively. |
| `test_missing_section_returns_none` | `get_section("Nonexistent Section")` is `None`. | Missing sections are tolerated, not errors. |
| `test_summary_text_includes_name_overview_and_tags` | `summary_text()` contains the name, an Overview word (`provisioned`), and a tag. | This string is the recommendation embedding — must carry the right signal. |
| `test_source_path_is_recorded` | `source_path` ends with the filename. | Traceability back to the source file. |
| `test_load_single_agent_directly` | `load_agent(path)` returns the right id and an Overview. | The single-file entry point works standalone. |

---

## 5. `tests/test_indexer.py` — Phase 2: indexing + retrieval (7 tests)

**Under test:** `src/index.py` (`build_index`) and `src/retriever.py`
(`search_agents`, `search_sections`). Builds a **real temp store**.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_index_builds_both_record_types` | `summary_records == agents`, `section_records > summary_records`. | The two-collection design (coarse summaries + fine sections) is built correctly. |
| `test_recommendation_query_returns_expected_agent` | "automate UI tests from a live URL" → top hit `test-script-generator`; score in `[0,1]`, best-first. | The headline acceptance criterion at the retrieval layer. |
| `test_metadata_filter_scopes_results` | `where={"autonomy_default":"L4"}` returns **only** L4 agents, and a known L4 agent is among them. | Metadata filtering ("fully autonomous") must scope precisely. |
| `test_section_search_is_scoped_to_agent_and_returns_section` | `search_sections` scoped to one agent returns only that agent's sections, each carrying its `section`, and `Inputs` is present. | The info path relies on agent+section scoping. |
| `test_section_filter_targets_a_single_section` | `$and` of `agent_id` + `section` returns only that exact section. | Precise targeting for grounded answers. |
| `test_list_frontmatter_flattened_into_scalar_metadata` | Lists (`tags`, `autonomy_supported`, `triggers`) are flattened to comma strings; `triggers_specified` bool is set. | Chroma metadata must be scalars; "specified" flag preserves the §8 distinction. |
| `test_reindex_rebuilds_cleanly_without_duplicates` | Re-running `build_index` yields the same counts and the live collection counts match. | "Re-index = clean rebuild," enabling no-code-change catalog updates. |

---

## 6. `tests/test_recommender.py` — Phase 3: recommendation (10 tests)

**Under test:** `src/recommender.py` (`recommend`, `detect_filter`). Mixes a real
temp store (clear-match / filtered) with `search_fn` stubs (threshold logic).

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_detect_filter` *(4 params)* | "fully autonomous"/"fully-automated" → `L4`; "L3 agent" → `L3`; a plain need → `None`. | Implied metadata filters are derived correctly. |
| `test_clear_single_match` | UI-automation query leads with `test-script-generator`; explanation names it. | A clear need produces the right single recommendation. |
| `test_metadata_filtered_query` | "fully autonomous" → only L4 agents returned. | Filter scoping at the recommendation layer. |
| `test_ambiguous_returns_shortlist` | Two stubbed hits within `AMBIGUITY_DELTA` → `ambiguous=True`, both returned, the far third excluded. | Comparable fits become a shortlist, not a forced pick. |
| `test_clear_match_when_runner_up_is_far_behind` | Top far above runner-up → single match, `ambiguous=False`. | The ambiguity threshold doesn't over-trigger. |
| `test_no_match_when_scores_too_low` | All hits below `NO_MATCH_SCORE` → `agents=[]`, "couldn't find". | Out-of-scope queries don't get a wrong recommendation. |
| `test_no_match_when_filter_matches_nothing` | A filter that matches nothing → `agents=[]`, `ambiguous=False`. | Empty filtered results are honest, not a crash. |

---

## 7. `tests/test_router.py` — Phase 4: intent routing (23 tests)

**Under test:** `src/router.py` (`detect_intent`, `find_agent`). Pure / catalog
file-read only — no embeddings, no network.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_detect_intent` *(13 params)* | Representative messages classify as `recommend` / `info` / `clarify` (incl. empty → clarify). | Routing is deterministic and accurate on real phrasing — no LLM call. |
| `test_definitional_question_about_named_agent_is_info` *(4 params)* | "What is X?", "Tell me about X", "Describe X" about a named agent → `info`. | Definitional phrasings about a real agent are lookups, not fall-throughs. |
| `test_find_agent` *(6 params)* | Names/ids in a message resolve to the right `agent_id`; cross-catalog asks → `None`. | Catalog-driven name detection (never hard-coded) scopes info/RAG. |

---

## 8. `tests/test_info.py` — Phase 4: RAG info path (18 tests)

**Under test:** `src/info.py` (`answer_question`, `detect_section`). Retriever is
**stubbed**; `use_llm=False` → deterministic fallback + grounding gate.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_detect_section` *(12 params)* | Question words map to the right section (`Inputs`, `Outputs`, `Autonomy Level`, `Deployment`, `Triggers`, `Limitations`); definitional → `Overview`; no attribute → `None`. | Correct section targeting is the precondition for grounded answers. |
| `test_definitional_question_answers_from_overview` | "Tell me about X" → grounded Overview answer, scoped via the agent+`Overview` `where` filter. | Bare definitional questions resolve to Overview. |
| `test_inputs_question_is_grounded_and_scoped` | An Inputs question → grounded answer drawn from the Inputs table, scoped to agent+section. | The core RAG behavior + precise scoping. |
| `test_outputs_question_is_grounded` | An Outputs question → grounded answer from the Outputs body. | Same, for another section. |
| `test_missing_deployment_is_not_hallucinated` | A `TBD` Deployment → `grounded=False`, "don't have", and **no** invented `gpu/cpu/ram/...`. | **The grounding gate** — the project's core safety property. |
| `test_not_specified_section_is_not_grounded` | "Not specified in source." → `grounded=False`. | The gate also covers the "not specified" placeholder. |
| `test_widens_when_section_filter_is_empty` | A too-tight agent+section filter returns nothing → the path widens to agent-only and still answers. | Retrieval resilience — a missed section doesn't dead-end. |
| `test_no_results_is_honest` | No hits at all → `grounded=False`, `sources=[]`. | Empty retrieval is honest, not a crash. |

---

## 9. `tests/test_chatbot.py` — Phase 5: orchestration / E2E (10 tests)

**Under test:** `src/chatbot.py` (`handle`, `available_agent_names`). Real temp
store for acceptance criteria; monkeypatched path functions for formatting edges.
This is where PROBLEM_STATEMENT §9 acceptance criteria are proven end to end.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_recommendation_returns_correct_agent` | "automate UI tests…" → reply names *Test Script Generator*. | §9: recommendation returns the correct agent. |
| `test_info_answer_is_grounded_in_the_right_section` | "inputs to Test Data Provisioning?" → "User Story ID" + source attribution. | §9: grounded info answer from the right section. |
| `test_definitional_question_is_grounded_in_overview` | "What is the User Story Analyser?" → Overview prose + `Source: … — Overview`. | Definitional E2E grounding + source line. |
| `test_missing_data_is_honest_not_fabricated` | "What hardware does the User Story Analyser need?" → real deployment facts + a `Source:` line. | §9: missing-data handling (and that filled-in data now answers). |
| `test_vague_message_triggers_clarification` | "hi" → a clarifying reply. | §9: vague → one clarifying question. |
| `test_new_agent_is_discoverable_after_reindex` | Adding a 5th agent + re-index → discoverable via search, no code change. | §9: catalog grows with zero code changes. |
| `test_no_match_lists_available_agents` *(stub)* | No-match recommend → "Available agents:" + every catalog name. | Edge formatting: a no-match lists the catalog. |
| `test_info_reply_attributes_its_source` *(stub)* | Grounded info → `Source: <name> — <section>`. | Grounded answers carry attribution. |
| `test_ungrounded_info_reply_has_no_source_line` *(stub)* | Ungrounded info → **no** `Source:` line. | Honest "don't have" must not look sourced. |
| `test_ambiguous_shortlist_is_surfaced` *(stub)* | Ambiguous recommend → both agents shown. | The shortlist reaches the user. |

---

## 10. `tests/test_llm.py` — Phase 6: LLM guardrails (10 tests)

**Under test:** the live LLM branches of `info.py` / `recommender.py` and the
`src/llm.py` contract — **fully mocked** (`monkeypatch` on `generate`), so no key,
network, or quota.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_available_true_with_key` / `test_available_false_without_key` | `llm.available()` reflects the env key. | The health flag and fallback decisions depend on this. |
| `test_generate_returns_none_without_key_and_never_raises` | No key → `generate()` returns `None`, never raises. | The fail-safe contract every caller relies on. |
| `test_generate_returns_none_when_client_build_fails` | A client failure → `None`, no raise. | Robustness against SDK/auth errors. |
| `test_info_uses_llm_text_when_available` | `generate()` text → surfaced as the answer (LLM branch taken). | The LLM path actually runs when available. |
| `test_info_falls_back_when_llm_returns_none` | `generate()` `None` → deterministic grounded fallback. | Graceful degradation to the offline path. |
| `test_info_treats_insufficient_context_sentinel_as_ungrounded` | LLM `INSUFFICIENT_CONTEXT` → `grounded=False`. | The second grounding guard (LLM admits it can't answer). |
| `test_grounding_gate_holds_under_llm_for_tbd_section` | **A fabricated GPU/RAM spec from the LLM does NOT leak on a `TBD` section** (`grounded=False`). | **The most important property** — the gate short-circuits before the model. |
| `test_recommend_uses_llm_explanation_when_available` | LLM text used as the explanation; right agent chosen. | Recommendation prose uses the LLM when available. |
| `test_recommend_falls_back_when_llm_returns_none` | Deterministic template names the agent. | Recommendation still works offline. |

---

## 11. `tests/test_api.py` — Phase 7: FastAPI backend (6 tests)

**Under test:** `api.py` via `fastapi.testclient.TestClient`; `use_llm=False`.
Real temp store for `/chat` retrieval.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_health_reports_ok_and_llm_flag` | `/health` → `status=ok`, `llm_available == llm.available()`. | Liveness + honest key state (not hard-coded). |
| `test_agents_lists_the_live_catalog` | `/agents` count + ids match the live catalog; each record has the agreed fields; `tags` is a list. | The catalog is read live and shaped per the contract. |
| `test_chat_recommendation_matches_handle` | `/chat` reply names the right agent **and equals** `handle(...)`. | Proves the API is a thin pass-through (no business logic). |
| `test_chat_vague_message_clarifies_without_store` | `/chat` "hi" → clarify, 200, no store needed. | Vague routing works at the HTTP layer. |
| `test_chat_use_llm_defaults_to_true` | Omitting `use_llm` → 200 with a reply. | The request-model default holds. |
| `test_cors_header_present_for_cross_origin_request` | A cross-origin request gets an `Access-Control-Allow-Origin` header. | Browser/Streamlit front ends can call the API. |

---

## 12. `tests/test_store.py` — caching & cache invalidation (4 tests)

**Under test:** `src/store.py` singletons and `refresh_catalog_caches()`. Uses
`temp_store` (temp path + reset singletons).

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_client_opened_once_across_searches` | `PersistentClient` is instantiated **exactly once** across two searches. | Performance: the client is a cached singleton, not re-opened per query. |
| `test_embedding_function_is_a_singleton` | `get_embedding_function()` returns the same object each call. | The expensive onnx wrapper is built once. |
| `test_new_agent_recognized_after_reindex` | A new agent is unknown before re-index, recognized after (no restart). | A long-running server reflects catalog changes after a re-index. |
| `test_refresh_clears_router_and_chatbot_caches` | `refresh_catalog_caches()` zeroes the `router._agent_terms` and `chatbot.available_agent_names` lru-caches. | Cache invalidation is wired correctly. |

---

## 13. `tests/test_logging.py` — tracing & secret safety (3 tests)

**Under test:** `src/logger.py` via pytest's `caplog`. LLM monkeypatched; one
temp store.

| Test | Checks | Why it matters |
|------|--------|----------------|
| `test_info_query_logs_full_trace` | An info query logs `INTENT DETECTED`, `AGENT IDENTIFIED`, `PROMPT SENT TO LLM`, `GROUNDING CHECK`, and the exact prompt. | The step-by-step trace a manager watches is actually emitted. |
| `test_tbd_query_logs_grounding_false` | A `TBD` section logs `GROUNDING CHECK: False`. | The grounding verdict is logged honestly. |
| `test_no_log_record_contains_a_secret` | **No log record contains `GEMINI_API_KEY` / `API_KEY`.** | Secrets are never logged — a hard safety guarantee. |

---

## 14. `tests/test_not_in_catalog.py` — the not-in-catalog grounding gate (21 tests)

**Under test:** the recommendation-path analogue of the TBD gate, spanning
`recommender._looks_like_specific_agent_request` / `asks_for_closest` /
`_not_in_catalog_message`, `router.agent_exists`, the `info.py` pre-check, and
`chatbot.handle` precedence. All offline (stubs / gate-before-retrieval).

**Why this suite exists:** when a user asks for a *specific named thing that isn't
in the catalog*, the bot must say "that agent may not exist yet" rather than (a)
recommending a loosely-similar agent, (b) answering about the wrong agent via a
shared word, or (c) emitting a generic no-match. It's the recommendation/info
counterpart of the grounding gate.

| Test(s) | Checks | Function(s) exercised |
|---------|--------|-----------------------|
| `test_unknown_named_agent_is_reported_not_in_catalog`, `test_not_in_catalog_reply_lists_available_agents`, `test_handle_reports_not_in_catalog` | "Is there a Performance Testing Agent?" → `not_in_catalog=True`, `agents=[]`, message says "development"/"not yet added" and lists the catalog. | `_looks_like_specific_agent_request`, `_not_in_catalog_message`, `recommend`, `handle` |
| `test_named_agent_in_catalog_takes_normal_path` | "I need the Data Coverage Agent" (real) → gate does **not** fire; normal recommendation. | `agent_exists`, `recommend` |
| `test_generic_need_is_not_a_false_positive`, `test_generic_ui_phrase_does_not_fire` | "I need to automate UI tests" → no false positive (too generic / short acronym). | capability detector guards |
| `test_capability_phrase_without_agent_word_fires`, `test_load_testing_capability_fires` | "Performance testing" / "Load testing" (no word *Agent*) → gate fires. | `_detect_uncataloged_capability` |
| `test_visual_regression_does_not_leak_wrong_agent_tbd` | "Do you have a Visual Regression Agent? …closest?" → not-in-catalog wins; **no** `TBD`/wrong-agent leak; closest surfaced. | `handle` precedence, `asks_for_closest` |
| `test_closest_match_appended_when_asked`, `test_closest_not_appended_below_threshold` | Closest alternative appended only when asked **and** above `NO_MATCH_SCORE`. | `recommend` closest logic |
| `test_info_question_for_nonexistent_agent_is_honest`, `test_info_path_short_message_has_no_agent_list` | "inputs to the Performance Testing Agent?" → honest short message, **no** wrong agent name (e.g. "Microsoft"), retriever not called. | `info.answer_question` pre-check |
| `test_real_agent_info_question_still_grounded` | A real agent still produces a grounded retrieved answer. | `answer_question` |
| `test_info_cicd_agent_is_honest_not_wrong_agent` | "What does the CI/CD Agent do?" → honest, no wrong-agent/`TBD` leak. | `handle` + info pre-check |
| `test_anything_called_nonexistent_agent_fires`, `test_anything_called_real_agent_does_not_fire` | "anything called the Bug Triaging Agent" fires; "…the Test Data Provisioning" (real) doesn't. | `_looks_like_specific_agent_request` |
| `test_security_scan_agent_handled` | "I need the security scan agent" → gate fires (file doesn't exist) and never returns a random shortlist. | `recommend` |
| `test_cicd_agent_output_extracts_clean_name`, `test_cicd_agent_output_reply_is_not_in_catalog`, `test_real_agent_output_question_does_not_fire` | Name extraction stops at predicate words: "CI/CD Agent output" → name `CI/CD` (not "CI/CD Agent output"); real agent doesn't fire. | `_tail_name` boundary trimming |

---

## 15. `tests/test_edge_cases.py` — system boundaries (27 tests)

**Under test:** the boundaries of every layer. Each test pins one failure mode to
an explicit expected behavior. Grouped A–F.

### Group A — Empty / missing catalog
| Test | Checks | Module |
|------|--------|--------|
| `test_a1_load_agents_on_empty_dir_returns_empty` | `load_agents()` on an empty dir → `[]`. | `loader` |
| `test_a2_build_index_on_empty_catalog_is_clean` | Empty catalog builds a clean store (0/0 records, no crash). | `index` |
| `test_a3_handle_with_empty_catalog_says_no_agents` | `handle()` with empty catalog → "No agents are currently available…". | `chatbot` |
| `test_a4_get_agents_with_empty_catalog_returns_empty` | `GET /agents` empty → `[]`, not a 500. | `api` |

### Group B — Malformed / partial files
| Test | Checks | Module |
|------|--------|--------|
| `test_b1_no_frontmatter_loads_with_stem_id` | No frontmatter → `agent_id` falls back to filename stem; body sections parsed. | `loader` |
| `test_b2_no_body_sections_loads_with_empty_sections` | Valid frontmatter, no body → `sections={}`. | `loader` |
| `test_b3_missing_section_returns_none` | Missing `## Deployment` → `get_section()` `None`. | `models` |
| `test_b4_malformed_yaml_falls_back_to_defaults` | Unterminated YAML string → loads with defaults, no crash. | `loader` (**fixed**) |

### Group C — Retrieval edges
| Test | Checks | Module |
|------|--------|--------|
| `test_c1_search_agents_on_empty_collection` | Search on an empty collection → `[]`. | `retriever` |
| `test_c2_search_sections_no_match_returns_empty` | A `where` matching nothing → `[]`. | `retriever` |
| `test_c2_info_path_widens_when_section_filter_empty` | Empty tight filter → info path widens and still answers. | `info` |
| `test_c3_very_long_query_returns_a_reply` | A >512-char query → a reply, no crash. | `chatbot` |
| `test_c4_special_characters_only_clarifies` | "???!!!@@@" → clarify, no crash. | `chatbot`/`router` |
| `test_c5_k_larger_than_catalog_returns_what_exists` | `k` larger than the catalog → returns what exists. | `retriever` |

### Group D — Info path edges
| Test | Checks | Module |
|------|--------|--------|
| `test_d1_all_sections_tbd_is_never_grounded` *(4 params)* | Every question about an all-`TBD` agent → `grounded=False`. | `info` |
| `test_d2_two_agent_names_picks_one_and_answers` | "compare X and Y" → picks one, answers, no crash. | `chatbot`/`info` |
| `test_d3_no_section_detected_still_answers` | No attribute word → `detect_section` `None`, path still answers. | `info` |

### Group E — Recommendation edges
| Test | Checks | Module |
|------|--------|--------|
| `test_e1_filter_matches_nothing_is_no_match` | A filter matching nothing → `agents=[]`, `ambiguous=False`, "match" message. | `recommender` |
| `test_e2_single_agent_catalog_recommends_it` | One-agent catalog → recommends it, no ambiguity crash. | `recommender` |
| `test_e3_unrelated_long_sentence_triggers_no_match` | A 50-word unrelated sentence → no-match. | `recommender` |

### Group F — API / interface edges
| Test | Checks | Module |
|------|--------|--------|
| `test_f1_chat_empty_message_returns_clarify` | `POST /chat` empty message → clarify, **not** 422. | `api` |
| `test_f2_chat_long_message_returns_reply` | `POST /chat` ~2000 chars → a reply. | `api` |
| `test_f3_chat_use_llm_omitted_defaults_true` | `use_llm` omitted → 200, not 422. | `api` |
| `test_f4_health_reports_llm_availability` | `/health` `llm_available == llm.available()` (not hard-coded). | `api` |

> **Fixes this suite drove** (each tagged `# EDGE CASE FIX:` in source):
> 1. `loader._split_frontmatter` — wrap `yaml.safe_load` in `try/except` (B4).
> 2. `chatbot._agent_list_block` — empty catalog states "no agents available" (A3).
> 3. `store.refresh_catalog_caches` — also clear `recommender._catalog_vocab`.

---

## 16. `frontend/tests/test_ui.py` — Phase 8: HTTP client (11 tests)

**Under test:** `frontend/api_client.py` (`call_chat`, `fetch_agents`,
`check_health`) with `requests.get`/`post` monkeypatched — **no live server, no
Streamlit session.** The client returns an `ApiResult` the UI can render; it must
never raise.

| Test | Checks |
|------|--------|
| `test_call_chat_normal_reply` | A 200 with `{reply}` → `ok=True`, `data` is the reply. |
| `test_call_chat_passes_use_llm_flag` | The `use_llm` flag is forwarded in the POST body. |
| `test_call_chat_api_down_returns_error` | `ConnectionError` → `ok=False`, helpful error naming `uvicorn api:app` and the base URL. |
| `test_call_chat_timeout_treated_as_unreachable` | `Timeout` → "not reachable". |
| `test_call_chat_non_200_returns_error` | A 500 → error includes the status and body. |
| `test_fetch_agents_normal` | `/agents` 200 → `data` is the agent list. |
| `test_fetch_agents_api_down` | `ConnectionError` → "not reachable". |
| `test_check_health_normal` | `/health` 200 → parsed status + `llm_available`. |
| `test_check_health_non_200` | A 503 → error includes the status. |
| `test_check_health_api_down` | `ConnectionError` → "not reachable". |
| `test_base_url_trailing_slash_normalized` | A trailing slash in the base URL is normalized (`…/health`). |

> The client **never imports `src`** — it talks to the API over HTTP only, so the
> UI can be swapped without touching the backend.

---

## 17. Coverage map — what proves what

| Concern | Where it's proven |
|---------|-------------------|
| §9 acceptance criteria (recommend / grounded info / honest missing / clarify / re-index discoverability) | `test_chatbot.py` |
| **Grounding gate** (no fabrication on `TBD`/empty) | `test_info.py`, `test_llm.py` (under LLM), `test_logging.py` (verdict logged) |
| **Not-in-catalog gate** (no wrong/loose answer for non-existent agents) | `test_not_in_catalog.py` |
| Two-collection design + metadata scoping | `test_indexer.py` |
| Threshold logic (no-match / shortlist) | `test_recommender.py` |
| Deterministic routing (no LLM for intent) | `test_router.py` |
| LLM-optional contract (`generate` → `None`, never raises) | `test_llm.py` |
| API thin-pass-through + CORS | `test_api.py` |
| Caching + cache invalidation after re-index | `test_store.py` |
| Secret safety in logs | `test_logging.py` |
| System boundaries (empty/malformed/oversized/edge inputs) | `test_edge_cases.py` |
| Frontend resilience (backend down, non-200) | `frontend/tests/test_ui.py` |

---

## 18. Conventions for adding tests

- One `test_<module>.py` per module; integration/E2E lives in `test_chatbot.py`;
  cross-cutting behaviors get a dedicated file (`test_not_in_catalog.py`,
  `test_edge_cases.py`).
- Default to `use_llm=False` and/or a `search_fn=` stub so tests stay offline and
  deterministic.
- Need a real store? Build into `tmp_path`/`tmp_path_factory` and restore
  `config.CHROMA_PATH` (and `config.AGENTS_DIR` if you swap the catalog) — never
  write to the repo's `.chroma/` or `agents/`.
- Assert on **facts and grounding**, not on exact LLM prose (which varies).
- When a catalog swap is involved, clear the catalog-derived caches
  (`router._agent_terms`, `chatbot.available_agent_names`,
  `recommender._catalog_vocab`).
