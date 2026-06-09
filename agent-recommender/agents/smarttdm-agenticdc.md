---
agent_id: smarttdm-agenticdc
name: SmartTDM AgenticDC
domain: testing
tags: [data-profiling, business-rules, synthetic-data, test-case-generation, coverage]
autonomy_default: L3          # inferred — source describes a HITL gate, not an explicit L-number
autonomy_supported: [L3]
triggers: []                  # not specified in source
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
Not specified in source.

## Deployment
**Hardware:** TBD
**Software:** TBD

## Limitations
Not specified in source.
