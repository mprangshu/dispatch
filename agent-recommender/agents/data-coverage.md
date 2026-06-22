---
agent_id: data-coverage
name: Data Coverage Agent
domain: testing
tags: [data-quality, coverage, business-rules, pii, combinatorial-testing, sensitivity, boundary-value]
autonomy_default: L2
autonomy_supported: [L1, L2, L3]
triggers: [manual, api]
---

## Overview
Identifies data sensitivity, hidden business rules, and patterns within datasets, then generates data coverage combinations mapped to test cases. Profiles each dataset's schema and sample values, classifies PII/PCI/HIPAA fields using an LLM, extracts hidden constraints and relationships (value ranges, conditional rules, uniqueness), and builds a pairwise, boundary-value, or equivalence-partitioning coverage matrix. The matrix can be linked to existing test cases for traceability. L1 returns sensitivity and rules only; L2 adds a HITL review gate before generating combinations; L3 runs the full pipeline autonomously.

## Autonomy Level
L2 · Supervised (default).

After inferring business rules, the agent pauses for the user to review sensitivity classifications and inferred rules. The user can approve, adjust rules in free text, or cancel. On approval the agent proceeds to generate the coverage matrix and map combinations to test cases.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Datasets | Yes | One or more datasets with schema, sample data, and source type (database, file, or API response) |
| Test Cases | No | Existing test cases to map coverage combinations against |
| Project | Yes | Scopes context retrieval, related dataset lookup, and report persistence |
| Combinatorial Method | No | pairwise, boundary-value, or equivalence-partitioning (default: pairwise) |
| Detect Sensitivity | No | Whether to classify PII/PCI/HIPAA fields (default: true) |
| Infer Business Rules | No | Whether to extract constraints and relationships (default: true) |

## Outputs
| Output | Description |
|--------|-------------|
| Sensitivity Report | PII, PCI, and HIPAA field classification per dataset with confidence and recommended handling |
| Business Rules | Extracted constraints, value ranges, conditional relationships, and uniqueness rules |
| Coverage Matrix | Combinatorial coverage combinations across the dataset's fields (L2/L3 only) |
| Test Case Mapping | Coverage combinations linked to provided test case IDs for traceability (L2/L3 only) |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Upload or reference datasets directly in the workspace |
| API | Submit datasets programmatically |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, MongoDB, outbound LLM access.

## Limitations
- PII classification depends on LLM accuracy; results should be reviewed before use in compliance contexts.
- Combinatorial matrix size grows rapidly with field count — very large datasets may require sub-sampling or column selection.
- L1 path does not generate coverage combinations or test case mappings.
- Business rule inference works best on datasets with meaningful sample data; empty or synthetic datasets yield fewer rules.
