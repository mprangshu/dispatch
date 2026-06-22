---
agent_id: api-test-script-generator
name: API Test Script Generator
domain: testing
tags: [api-testing, swagger, openapi, playwright, script-generation, test-execution, self-healing]
autonomy_default: L2
autonomy_supported: [L2]
triggers: [manual, api]
---

## Overview
Generates and executes Playwright TypeScript test scripts from a Swagger/OpenAPI specification. Takes a Swagger file (upload, URL, or previously saved spec), parses all endpoints, detects spec changes against a prior project snapshot (healer mode), lets the user select endpoints and edit definitions at a HITL gate, generates 3–5 test cases per endpoint via LLM, requests user approval before executing them against the real API, generates final Playwright spec files using execution results, runs the scripts, and auto-heals failing body assertions where the HTTP status code matched the spec. Status-code mismatches are left failing intentionally — those are real spec violations.

## Autonomy Level
L2 · Supervised.

Two HITL checkpoints: endpoint selection (with per-endpoint URL/header/payload edits), and test-case approval before any real API calls are made. The body-assertion healer runs autonomously after script execution.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Swagger/OpenAPI Spec | Yes | File upload, hosted URL (http/https), or the name of a previously saved spec in the project |
| Target Framework | Yes | Test framework to generate scripts for (e.g. playwright-typescript) |
| Project | Yes | Scopes spec versioning, context retrieval, and script persistence |
| Execute Test Cases | No | Whether to execute generated test cases against the real API before scripting (default: true) |

## Outputs
| Output | Description |
|--------|-------------|
| API Definition Table | Parsed endpoint definitions (path, method, params, payload) shown for selection and optional per-endpoint editing |
| Test Case Table | Generated test cases shown for user approval before any API calls |
| Execution Results | Per-test-case results with actual status codes and response data (titled "Test Case Validation Results") |
| Code Viewer | Final Playwright TypeScript spec files per endpoint, tagged generated, executed, or healed |
| Playwright Results | Per-spec test run results after script execution, with pass/fail and error details |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Upload or reference a Swagger spec in the workspace |
| API | Submit the spec and configuration programmatically |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, Node.js 18+ (for `npx playwright`), outbound access to the target API and LLM endpoint.

## Limitations
- Script execution requires a reachable target API; the agent cannot produce execution results for offline or mock-only APIs.
- Body assertion healing only applies where the status code matched the spec; genuine spec violations are preserved as failures.
- Swagger 2.0 formData encoding and OpenAPI 3.0 are supported; extended JSON Schema keywords beyond these versions may not parse correctly.
- Change-detection (healer mode) requires a prior saved snapshot for the same project and filename; first-ever runs treat all endpoints as new.
