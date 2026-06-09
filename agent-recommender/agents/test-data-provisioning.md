---
agent_id: test-data-provisioning
name: Test Data Provisioning
domain: testing
tags: [test-data, provisioning, synthetic-data, tdr, export]
autonomy_default: L2
autonomy_supported: [L1, L2, L3]
triggers: []                  # not specified in source
---

## Overview
Given a User Story ID, this agent provisions ready-to-use test data for the
associated test cases. It:

- Discovers all test cases linked to the user story.
- Identifies the test data fields each test case needs (via an LLM, or from
  existing knowledge graph metadata).
- Lets the user confirm/edit the fields and their filter criteria.
- Mines real test data from the Test Data Repository (TDR) and generates
  synthetic data for any new fields.
- Exports the final dataset as CSV or JSON.

## Autonomy Level
L2 (default) · Supported: L1, L2, L3.

| Level | Behaviour |
|-------|-----------|
| L1 | Fields identified; user confirms all details manually. |
| L2 | Fields auto-identified; user confirms selection; data mining runs automatically. |
| L3 | End-to-end, including saving the configuration to the knowledge graph if approved. |

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Story ID | Yes | Identifies the story whose linked test cases need data |
| Autonomy level | Yes | Which level to run at: L1, L2, or L3 |
| User confirmations | Yes | In-run choices: field selection, save-config choice, and continue-or-download choice |

## Outputs
| Output | Description |
|--------|-------------|
| Test dataset | A provisioned dataset (mined + synthetic data merged) for each test case |
| Export file | The dataset as a downloadable CSV or JSON file |
| Saved configuration | Optionally, the test configuration (fields/schema) stored against the test case for future reuse |

## Triggers
Not specified in source.

## Deployment
**Hardware:** TBD
**Software:** TBD

## Limitations
Not specified in source.
