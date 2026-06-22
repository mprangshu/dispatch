---
agent_id: impact-analyzer-supervisor-l4
name: Impact Analyzer — Supervisor L4
domain: testing
tags: [impact-analysis, test-prioritization, release, knowledge-graph, neo4j, supervisor, react-agent]
autonomy_default: L4
autonomy_supported: [L4]
triggers: [manual, api, webhook]
---

## Overview
Analyses a software release to determine which test cases must run, prioritising them by impact category. Built with `create_supervisor` orchestrating four `create_react_agent` sub-agents: KnowledgeGraph (loads release data, runs vector similarity search in Neo4j, and scores Chronic and Config categories), Analysis (classifies each test case as Direct, Indirect, Core, Repair, Chronic, or Config), Reviewer (validates prioritisation decisions and triggers self-correction), and Explanation (generates human-readable rationale per decision). KnowledgeGraph and Analysis run deterministic ReAct loops (no LLM); Reviewer and Explanation run LLM-powered loops. Historical failure data is read from HCM CSV files. The agent publishes the prioritised test list and a review report via write-confirmation gate.

## Autonomy Level
L4 · Delegatory.

The agent runs the full KG-load → Analysis → Review → Explanation pipeline autonomously. The user is prompted only for final write-confirmation before publishing results. Self-correction on Reviewer failure re-routes Analysis with adjusted similarity thresholds (up to 3 retries).

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Input | Yes | Natural language request, e.g. "Analyze release R_07 and publish results" |
| CSV Directory | Yes | Path to folder containing HCM_*.csv historical failure and config data files |
| Project | Yes | Scopes KG namespace, embedding index, and result persistence |
| Release ID | No | Extracted from user input if not provided explicitly |
| Similarity Threshold | No | Override per-category similarity threshold (default: agent-managed) |
| Include Chronic | No | Whether to score Chronic category (default: true) |
| Include Config | No | Whether to score Config category (default: true) |

## Outputs
| Output | Description |
|--------|-------------|
| Prioritized Test Table | Test cases with priority (High/Medium/Low), impact category (Direct/Indirect/Core/Repair/Chronic/Config), similarity or chronic score, and a RUN/SKIP decision with one-sentence rationale |
| Review Report | Quality gate findings and any self-correction adjustments from the Reviewer sub-agent |
| Impact Summary | High-level summary of the release's overall test impact scope |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Describe the release and provide the CSV directory path in the workspace |
| API | Submit release ID and CSV path programmatically |
| Webhook | Triggered by a CI pipeline event on release creation |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, `langgraph-supervisor`, Neo4j access (vector index required for similarity scoring), outbound LLM access.

## Limitations
- Chronic and Config category scoring requires HCM CSV files; missing or malformed files cause those categories to be skipped.
- Similarity scoring accuracy depends on the quality and completeness of test case embeddings in Neo4j; a sparsely-populated graph reduces precision.
- Self-correction is bounded at 3 Reviewer retries; persistent failures exit with a partial result.
- Direct and Indirect classification requires the KG to contain release-to-test-case linkage data.
