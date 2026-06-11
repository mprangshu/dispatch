---
agent_id: smarttdm-agenticdc
name: SmartTDM AgenticDC
domain: testing
tags: [data-profiling, business-rules, synthetic-data, test-case-generation, coverage]
autonomy_default: L3          # inferred — source describes a HITL gate, not an explicit L-number
autonomy_supported: [L3]
triggers: [manual, api]
---

## Overview
SmartTDM AgenticDC is an AI-powered agentic system that connects to databases,
extracts business rules using LLMs, validates them, and auto-generates test cases
with synthetic data. It works in three stages:

- **Data Profiling** — connects to the database, samples table data, and builds
  statistical profiles (distributions, domains, dependencies).
- **Rule Extraction & Validation** — uses an LLM to generate business rules from
  the profiles, then validates each rule against a set of automated checks.
- **Test Case & Synthetic Data Generation** — after human review of the rules,
  generates synthetic data and test cases, then measures and refines coverage
  against a target threshold.

## Autonomy Level
L3 · Goal-driven with a human-in-the-loop (HITL) review gate.

Stages 1 and 2 (profiling, rule extraction, validation) run automatically. A HITL
review gate sits between rule validation and test case generation — a person reviews
the validated rules before stage 3 (test case and synthetic data generation) is
triggered.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Database connection | Yes | The database to analyse, referenced by a connection ID |
| Table names | Yes | The tables to analyse |
| Coverage threshold | Yes | The target test coverage the run should reach |
| Rule approval | Yes | Human sign-off on the validated rules at the HITL review gate, before stage 3 |

## Outputs
| Output | Description |
|--------|-------------|
| Business rules | Extracted and validated business rules |
| Synthetic data | Generated synthetic data |
| Test cases | Auto-generated test cases |
| Coverage report | Measures achieved test coverage against the threshold |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Launch a run from the workspace by selecting a database connection, tables, and coverage threshold |
| API | Trigger profiling-to-generation programmatically via the run endpoint |

## Deployment
**Hardware:** 4 vCPU, 16 GB RAM, and ~50 GB free disk for profiling large tables and staging generated data.
**Software:** Python 3.11+, database drivers for the connected source (e.g. PostgreSQL/MySQL/Oracle), and LLM API access for rule extraction.

## Limitations
- Rule-extraction quality depends on representative data samples; sparsely populated tables yield weaker rules.
- Very wide schemas may not reach the target coverage threshold within the default iteration budget.
- Requires read access to production-like data; it does not operate on schema-only (empty) databases.
