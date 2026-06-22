---
agent_id: regression-healing-deepagent
name: Regression Healing (DeepAgent)
domain: automation
tags: [regression, self-healing, playwright, deepagent, batch, knowledge-base, script-repair]
autonomy_default: L4
autonomy_supported: [L4]
triggers: [manual, api, webhook]
---

## Overview
Batch-heals failed Playwright regression test scripts using the DeepAgent SDK. Given a set of failed scripts (1–1000), the agent analyses each failure, searches a persistent Knowledge Base for previously resolved failures with matching signatures, applies known fixes when found, and invokes the DeepAgent LLM reasoning loop to generate and verify new repairs when no prior resolution exists. Successfully resolved failures are written back to the Knowledge Base. The current v1 scope covers UI/locator/script errors (F1 class); logic failures, environment failures, and test data failures are out of scope for this version.

## Autonomy Level
L4 · Delegatory.

The agent processes the full batch autonomously. No HITL gates in the healing loop — the user launches with a set of failed scripts and receives healed scripts and a batch summary. The Knowledge Base is updated silently on each successful resolution.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Failed Test Scripts | Yes | One or more Playwright TypeScript test files that failed in the regression suite (1–1000 scripts per batch) |
| Failure Report | No | CI failure log or JSON artifact from the regression run; agent parses failure signatures if provided |
| Project | Yes | Scopes Knowledge Base namespace and healed script storage |

## Outputs
| Output | Description |
|--------|-------------|
| Healed Scripts | Repaired Playwright TypeScript test files replacing the originals |
| Batch Summary | Per-script outcome: healed (KB hit), healed (new repair), or unresolved — with a brief rationale for each |
| Knowledge Base Updates | New resolved-failure patterns written to the project's Knowledge Base for future batch reuse |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Upload failed scripts or reference a failed test run in the workspace |
| API | Submit a list of failed script paths programmatically |
| Webhook | Triggered automatically by a CI pipeline on regression failure |

## Deployment
**Hardware:** 4 vCPU, 8 GB RAM recommended for large batches; no GPU required.
**Software:** Python 3.11+, DeepAgent SDK, Node.js 18+ (for Playwright re-execution), PostgreSQL (required for Knowledge Base persistence), outbound LLM access.

## Limitations
- v1 scope is F1 class failures only: UI/locator errors, element-not-found, script syntax errors. Logic failures (wrong assertions), environment failures (network, auth), and test data failures are not healed and reported as unresolved.
- PostgreSQL is required for the Knowledge Base; the agent will not start without a reachable PostgreSQL instance.
- Batch size is capped at 1000 scripts per invocation; larger suites must be split into multiple runs.
- Healing accuracy improves over time as the Knowledge Base accumulates resolved patterns; early runs with an empty KB will have a lower KB-hit rate.
