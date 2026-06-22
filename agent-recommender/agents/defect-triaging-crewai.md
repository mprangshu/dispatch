---
agent_id: defect-triaging-crewai
name: Defect Triaging (CrewAI)
domain: testing
tags: [defect, triage, root-cause, log-analysis, neo4j, azure-devops, crewai, flow, parallel]
autonomy_default: L2
autonomy_supported: [L2]
triggers: [manual, api, webhook]
---

## Overview
A parallel CrewAI Flow-based implementation of the defect triaging workflow — same business logic as the LangGraph Defect Triaging agent but orchestrated via CrewAI's `@start`/`@listen`/`@router`/`and_`/`or_` DAG. Runs text extraction and image analysis in parallel fan-out (`and_`) and handles log filter branch choices naturally via `or_()`. A CrewAI ReAct sub-agent handles log source lookup and search with full tool-calling capability. Same Neo4j schema, ADO endpoints, OpenSearch contract, and prompts as the LangGraph sibling; all frontend GenUI components are fully reused. This agent demonstrates the platform's framework-agnostic agent integration model — choose it over the LangGraph variant when parallel fan-out and explicit DAG routing are preferred.

## Autonomy Level
L2 · Supervised.

Same HITL structure as the LangGraph variant: log review and selection, continue-to-analysis decision, resolution publishing confirmation, and final coder assignment. HITL is implemented via `asyncio.Future` resolution (not LangGraph interrupt/Command).

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Defect | Yes | Defect ID for Neo4j lookup, or manual input (description, reproduce steps, detected date) |
| Log File Path | No | Path to a local log file when Neo4j log source is unavailable (manual input mode) |
| Project | Yes | Scopes Neo4j namespace, ADO project, and OpenSearch index |

## Outputs
| Output | Description |
|--------|-------------|
| Log Analysis | Filtered and user-selected logs published as comments on the ADO work item |
| Root Cause Analysis | Categorised root cause (Application Code / Test Data / Environment), parsed identifiers, log correlation, and resolution steps |
| Assignment | Defect assigned to the identified responsible coder in Azure DevOps |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Enter defect details or a defect ID directly in the workspace |
| API | Submit a defect ID programmatically |
| Webhook | Triggered when a new defect is created in the tracking system |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, `crewai>=0.70.0`, Neo4j access (knowledge graph + vector index), OpenSearch/Kibana access, Azure DevOps API access, outbound LLM access.

## Limitations
- L1 and L3 autonomy levels are deferred to Phase 2; currently L2 only.
- Parallel fan-out (text + image extraction) increases peak LLM usage compared to the sequential LangGraph variant.
- Same data-access requirements as the LangGraph sibling: Neo4j, log sources, and ADO credentials all required.
- Image analysis is skipped in manual input mode (no attached images from form input).
