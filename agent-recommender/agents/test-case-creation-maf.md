---
agent_id: test-case-creation-maf
name: Test Case Creation — Microsoft Agent Framework
domain: testing
tags: [test-cases, user-story, microsoft-agent-framework, maf, workflow, deterministic-routing]
autonomy_default: L4
autonomy_supported: [L4]
triggers: [manual, api, webhook]
---

## Overview
A test case creation agent built on the Microsoft Agent Framework (MAF) Functional Workflow API. The supervisor is a plain `async def` Python function with deterministic `while`/`if` routing — no LLM router — orchestrating three `@step`-decorated workers: Planner (fetch requirement → extract scenarios → compare coverage → generate plan), Executor (execute plan actions via a single mega-tool, emits test-case-table GenUI), and Reviewer (validate completeness, data coverage, correctness; produce review report). HITL is handled via an `asyncio.Queue` rather than LangGraph's interrupt/resume mechanism. LLM calls go through the platform's `build_llm()` factory (LangChain), supporting Anthropic, Azure OpenAI, and Gemini.

## Autonomy Level
L4 · Collaborative.

Routing between workers is deterministic; the user is prompted at two HITL checkpoints: plan approval before execution, and test-case review/edit before finalisation. Self-correction on Reviewer FAIL re-runs the Executor with correction tasks, up to 3 iterations.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Story | Yes | Raw story text or Jira story ID |
| Acceptance Criteria | No | Extracted from the story if not provided |
| Project | Yes | Scopes context retrieval, existing test lookup, and persistence |
| Jira Story ID | No | Explicit Jira ID for webhook/API triggers that supply a story ID rather than raw text |
| Priority | No | Default priority for generated cases: High, Medium, or Low |
| Include Edge Cases | No | Whether to include edge and boundary scenarios (default: true) |
| Test Types | No | Subset of Positive, Negative, Edge, Boundary (default: all) |

## Outputs
| Output | Description |
|--------|-------------|
| Test Case Table | Structured test cases with ID, title, description, priority, type, numbered steps, CREATE/UPDATE/SKIP decision, and decision rationale |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Paste the user story directly in the workspace |
| API | Submit a story programmatically |
| Webhook | Triggered automatically when a new story is created or updated in Jira |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, `agent-framework>=1.0.0`, MongoDB, outbound LLM access.

## Limitations
- Routing is deterministic (no LLM supervisor); complex edge cases in routing may require code changes rather than prompt tuning.
- HITL uses `asyncio.Queue`; if the WebSocket connection drops during a checkpoint the run must be restarted.
- Self-correction is capped at 3 Executor iterations; unresolved review failures exit best-effort.
