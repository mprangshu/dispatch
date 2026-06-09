---
agent_id: user-story-analyser
name: User Story Analyser Agent
domain: testing
tags: [user-story, requirements, quality-scoring, acceptance-criteria, jira]
autonomy_default: L3
autonomy_supported: [L3]
triggers: [manual, api, webhook]
---

## Overview
The User Story Analyser reviews a user story and tells you exactly what is wrong
with it — then fixes it. It scores the story against a quality framework, gathers
missing context from your project, rewrites the story to a higher standard, and
generates structured acceptance criteria. At three points during the process, it
pauses and asks for your input before moving forward.

## Autonomy Level
L3 · Goal-driven.

The agent runs toward the goal of a refined, well-scored story, but pauses at three
points during the process to ask for the user's input before continuing.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Story | Yes | Paste the raw story text directly, or the agent fetches it from Jira automatically (webhook/API trigger) |
| Project | Yes | Determines which project's context, past stories, and test suites are used |
| Score Threshold | No | The minimum quality score each criterion must reach (default: 7 out of 10) |
| Criteria Focus | No | Limit scoring to specific criteria if you only care about certain quality dimensions |
| Additional Context | No | Any extra notes or business context to consider during the rewrite |

## Outputs
| Output | Description |
|--------|-------------|
| Quality Scorecard | Scores the story across 10 quality criteria (INVEST + QEA framework). Each criterion includes a score, the reason for it, and a recommended improvement; recommendations can be toggled on or off |
| Context Sources | Documents and test suites the agent gathered to fill identified gaps, each with source, a short extract, and a relevance score |
| Refined Story | The original and rewritten story shown side by side, in standard "As a / I want / So that" format |
| Acceptance Criteria Table | Structured functional and non-functional acceptance criteria, each linked to the quality dimension that produced it |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Paste a story directly in the workspace |
| API | Submit a story programmatically via API |
| Webhook | Automatically triggered when a new story is created in Jira |

## Deployment
**Hardware:** TBD
**Software:** TBD

## Limitations
Not specified in source.
