---
agent_id: api-contract-validator
name: API Contract Validator Agent
domain: testing
tags: [api-testing, contract-testing, openapi, schema-validation, regression]
autonomy_default: L2
autonomy_supported: [L1, L2, L3]
triggers: [manual, api, webhook]
---

## Overview
The API Contract Validator checks that a running API still honours its published
contract. You point it at an OpenAPI/Swagger specification and a base URL; the
agent generates requests for each documented endpoint, calls the live service,
and validates every response against the schema — status codes, headers, required
fields, and types. It flags breaking changes (removed fields, tightened types,
changed status codes) and produces a contract-compliance report, making it well
suited to catching regressions in CI before they reach consumers.

## Autonomy Level
L2 (default) · Supported: L1, L2, L3.

| Level | Behaviour |
|-------|-----------|
| L1 | Generates the request set; the user reviews and approves before any calls are made. |
| L2 | Calls endpoints and validates responses automatically; the user reviews the findings. |
| L3 | End-to-end, including opening a ticket for each confirmed breaking change. |

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| OpenAPI spec | Yes | The contract to validate against (URL or uploaded `.yaml`/`.json`) |
| Base URL | Yes | The live API base URL the agent sends requests to |
| Auth token | No | Bearer/API-key credential for protected endpoints |
| Endpoint filter | No | Limit validation to specific paths or tags instead of the whole spec |

## Outputs
| Output | Description |
|--------|-------------|
| Compliance report | Per-endpoint pass/fail against the contract, with the specific schema violation for each failure |
| Breaking-change list | Removed fields, tightened types, and changed status codes detected against the spec |
| Request/response log | The exact requests sent and responses received, for debugging |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Provide a spec and base URL directly in the workspace |
| API | Start a validation run programmatically via the run endpoint |
| Webhook | Automatically validate on each deploy when wired to a CI/CD webhook |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, outbound network access to the target API, and read access to the OpenAPI spec source.

## Limitations
- Validates against what the contract documents; behaviour that the spec omits cannot be checked.
- Cannot exercise endpoints that require interactive or multi-step human authentication.
- Stateful flows (create-then-read across endpoints) are validated per-endpoint, not as end-to-end sequences.
