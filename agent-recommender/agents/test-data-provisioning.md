---
agent_id: test-data-provisioning
name: Test Data Provisioning
domain: testing
tags: [test-data, provisioning, neo4j, hsqldb, synthetic-data, data-mining, knowledge-graph]
autonomy_default: L2
autonomy_supported: [L1, L2, L3]
triggers: [manual, api, webhook]
---

## Overview
Given a User Story ID, discovers all associated test cases from the Neo4j knowledge graph, identifies the test data fields required per test case (via LLM or existing KG metadata), mines real data from a HSQLDB Test Data Repository, generates synthetic data for fields with no real source, and exports the final provisioned dataset as CSV or JSON. The agent iterates through each test case with three HITL checkpoints: field selection and filter confirmation, save-config decision, and continue-or-download choice. PII is scrubbed from all mined data before display.

## Autonomy Level
L2 · Supervised (default).

Three HITL checkpoints per test case: the user reviews and selects identified data fields (with optional filter edits), decides whether to save the field configuration for future use, and chooses whether to continue to the next test case or download now.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Story ID | Yes | Identifier to look up associated test cases in the Neo4j knowledge graph |
| Project | Yes | Scopes KG namespace, TDR connection, and data persistence |

## Outputs
| Output | Description |
|--------|-------------|
| Test Case Accordion | List of discovered test cases from the knowledge graph, shown before data mining begins |
| Test Data Table | Mined and generated data rows per test case, shown for review after each mining cycle |
| Download Package | Final provisioned dataset exported as CSV and/or JSON, available for download |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Enter a User Story ID in the workspace |
| API | Submit a User Story ID programmatically (planned) |
| Webhook | Triggered when test cases are linked to a user story (planned) |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; JVM required for HSQLDB JDBC access.
**Software:** Python 3.11+, Java 11+ (JVM for jaydebeapi/JPype1 JDBC bridge), HSQLDB Test Data Repository access, Neo4j connection for knowledge graph.

## Limitations
- Requires an accessible HSQLDB Test Data Repository for real data mining; falls back to synthetic generation only when the TDR is unreachable.
- PII is scrubbed from mined data before display; production data sources must be configured with appropriate access controls.
- The knowledge graph must contain test case metadata for the given User Story ID; sparse graphs yield fewer or no test cases.
- JVM startup via JPype1 adds a cold-start delay on first run.
