---
agent_id: test-case-creation-supervisor-l4
name: Test Case Creation — Supervisor L4
domain: testing
tags: [test-cases, user-story, supervisor, langgraph, create-supervisor, react-agent, coverage]
autonomy_default: L4
autonomy_supported: [L4]
triggers: [manual, api, webhook]
---

## Overview
An advanced test case creation agent built with `create_supervisor` orchestrating three `create_react_agent` workers — Planner, Executor, and Reviewer. Unlike the hand-rolled graph variant, each worker runs its own autonomous ReAct loop: the Planner fetches the requirement, extracts scenarios, compares coverage in a single batch call, and produces a test plan with CREATE/UPDATE/SKIP decisions; the Executor calls a single mega-tool to process all plan actions at once; the Reviewer runs completeness and correctness quality gates and returns PASS or FAIL to the Supervisor. Guardrails are embedded in the prompt layer rather than as separate LangGraph nodes. New tools can be added to any worker without graph rewiring.

## Autonomy Level
L4 · Collaborative.

Workers run their ReAct loops autonomously. The user is prompted at two HITL checkpoints: plan review before execution begins, and test-case approval before the final output is confirmed. Self-correction on Reviewer FAIL re-routes to the Executor with adjusted context.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Story | Yes | Raw story text or Jira story ID (webhook/API triggers) |
| Acceptance Criteria | No | Extracted from the story if not provided |
| Project | Yes | Scopes context retrieval, existing test lookup, and persistence |
| Priority | No | Default priority for generated cases: High, Medium, or Low |
| Include Edge Cases | No | Whether to include edge and boundary scenarios (default: true) |
| Test Types | No | Subset of Positive, Negative, Edge, Boundary (default: all) |

## Outputs
| Output | Description |
|--------|-------------|
| Test Case Table | Structured test cases with ID, title, description, priority, type, numbered steps, CREATE/UPDATE/SKIP decision, and a one-sentence decision rationale per case |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Paste the user story directly in the workspace |
| API | Submit a story programmatically |
| Webhook | Triggered automatically when a new story is created or updated in Jira |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, `langgraph-supervisor`, MongoDB, outbound LLM access.

## Limitations
- The Executor processes all plan actions in a single mega-tool call; partial failures may affect the entire batch.
- Worker ReAct loops are bounded but can produce variable token usage on complex or ambiguous stories.
- Coverage comparison uses a batch call across all scenarios; very large test suites may approach context limits.
