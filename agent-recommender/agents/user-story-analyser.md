---
agent_id: user-story-analyser
name: User Story Analyser
domain: requirements
tags: [user-story, requirements, quality-scoring, acceptance-criteria, jira, react-agent, invest]
autonomy_default: L3
autonomy_supported: [L3]
triggers: [manual, api, webhook]
---

## Overview
Reviews a user story end-to-end and fixes it. Scores the story against a 10-criterion quality framework (INVEST + QEA), gathers missing context from the project's knowledge base, rewrites the story to a higher standard, and generates structured acceptance criteria. Runs as a single ReAct agent — no HITL checkpoints. A self-correction loop retries internally up to 2 times if any criterion scores below the threshold. At each phase the agent emits interactive GenUI panels: a quality scorecard with toggleable recommendations, a context sources panel, a side-by-side story comparison, and an acceptance criteria table.

## Autonomy Level
L3 · Goal-driven.

The agent runs fully autonomously from receipt of the story to delivery of the refined output. No user checkpoints during execution; the self-correction loop is internal. Users interact after the run via the interactive scorecard (toggling recommendations on/off) and review the refined story before accepting it.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Story | Yes | Raw story text (manual trigger) or Jira story ID (webhook/API trigger) |
| Project | Yes | Scopes context retrieval, past story lookup, and persistence |
| Score Threshold | No | Minimum quality score per criterion (default: 7 out of 10) |
| Criteria Focus | No | Limit scoring to specific criterion IDs; defaults to all 10 |
| Additional Context | No | Extra business context injected before analysis |

## Outputs
| Output | Description |
|--------|-------------|
| Quality Scorecard | Scores across 10 criteria (INVEST + QEA) with reason, actionable recommendation, and a user-controlled toggle per criterion |
| Context Sources | Documents and test suites gathered to fill identified gaps, with source URL, short extract, and relevance score |
| Story Review Panel | Original and refined story shown side by side in "As a / I want / So that" format |
| Acceptance Criteria Table | Structured functional and non-functional ACs, each linked to the quality criteria that produced it |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Paste story text directly in the workspace |
| API | Submit a story programmatically |
| Webhook | Triggered when a new story is created in Jira |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, Jira Cloud/Server API access for story fetch and webhook triggers, outbound LLM access.

## Limitations
- Quality scoring is tuned for English-language stories; other languages may score less reliably.
- Non-text attachments (images, diagrams) are ignored — only the story text and reachable project context are analysed.
- Self-correction retries at most 2 times; if criteria still fall short, the result is flagged as best-effort with failing criteria listed.
- Context gathering depends on the project's knowledge base being populated; sparse projects reduce rewrite quality.
