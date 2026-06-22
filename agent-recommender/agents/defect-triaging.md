---
agent_id: defect-triaging
name: Defect Triaging
domain: testing
tags: [defect, triage, root-cause, log-analysis, neo4j, azure-devops, ado, multimodal, langgraph]
autonomy_default: L2
autonomy_supported: [L1, L2, L3]
triggers: [manual, api, webhook]
---

## Overview
Automates end-to-end defect analysis, root cause identification, and assignment. Given a defect (from Neo4j or manual input), the agent gathers defect context, extracts key identifiers from text and attached images in parallel (multimodal LLM), searches and filters logs via Neo4j component lookup (dispatching to OpenSearch/Kibana or local file search), finds similar defects via vector similarity search (cosine > 0.85, < 0.99), performs LLM-based root cause analysis categorised as Application Code Issue / Test Data Issue / Environment Issue, publishes findings to Azure DevOps, and assigns the defect to the responsible owner via Neo4j graph traversal (Defect → Test Case → User Story → Document → Coder). Multiple HITL checkpoints let the user control log selection, analysis continuation, resolution publishing, and final coder assignment.

## Autonomy Level
L2 · Supervised (default).

Multiple user-facing HITL gates through the pipeline: log selection and publish to ADO; continue-to-analysis decision; resolution publishing confirmation; proceed-to-assignment decision; and final coder selection from a dropdown before ADO update.

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
**Software:** Python 3.11+, LangGraph 1.0+, Neo4j access (knowledge graph + vector index), OpenSearch/Kibana access (log search), Azure DevOps API access, outbound LLM access.

## Limitations
- Owner identification via Neo4j graph traversal applies only to Application Code Issue; Test Data and Environment issues require manual coder assignment.
- Similar-defect search is skipped in manual input mode (no graph embedding to query against).
- Log search requires either OpenSearch/Kibana or accessible local log files; missing log sources skip that phase.
- Image analysis (multimodal LLM) is only triggered when defect attachments are present.
