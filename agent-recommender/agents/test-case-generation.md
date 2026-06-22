---
agent_id: test-case-generation
name: Test Case Generation
domain: testing
tags: [test-cases, user-story, acceptance-criteria, jira, multi-agent, langgraph, supervisor]
autonomy_default: L4
autonomy_supported: [L4]
triggers: [manual, api, webhook]
---

## Overview
A multi-agent pipeline that converts a user story into a reviewed, structured set of test cases. A Supervisor orchestrates three specialist sub-agents: the Planner decomposes acceptance criteria into test scenarios and assigns CREATE/UPDATE/MERGE/SKIP decisions against existing cases, the Executor generates or updates test cases using templates and project context, and the Reviewer validates completeness (100% AC coverage) and correctness (< 20% redundancy). The Supervisor self-corrects on review failure up to 2 times. Two HITL checkpoints pause execution: test-plan approval before generation, and write-confirmation before each system update.

## Autonomy Level
L4 · Collaborative.

The agent plans, generates, and reviews test cases autonomously. The user approves the test plan before generation begins, and confirms each write action (create or update) to the test management system. Self-correction between Executor and Reviewer requires no user input.

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
| Scenario List | Intermediate GenUI view of the Planner's test plan, shown before generation for HITL approval |
| Test Case Table | Structured test cases with ID, title, description, priority, type, and numbered action/expected steps; each case shows its CREATE/UPDATE/SKIP decision with a one-sentence rationale |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Paste the user story directly in the workspace |
| API | Submit a story programmatically |
| Webhook | Triggered automatically when a new story is created or updated in Jira |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, MongoDB, outbound LLM access, Jira Cloud/Server API access for story fetch (webhook/API triggers).

## Limitations
- Self-correction is capped at 2 retries; if the Reviewer still fails the run exits as best-effort.
- Test generation quality depends on the completeness of the user story and the project's existing context.
- Merge and deduplication decisions rely on vector similarity; very similar stories may produce overlapping cases.
- The Executor uses `HumanInTheLoopMiddleware` for write confirmation; disabling this bypasses audit trail for system updates.
