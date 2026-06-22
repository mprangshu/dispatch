---
agent_id: test-script-generator
name: Test Script Generator (Playwright MCP)
domain: automation
tags: [playwright, script-generation, e2e, mcp, web-testing, self-healing, pipeline]
autonomy_default: L4
autonomy_supported: [L4]
triggers: [manual, api]
---

## Overview
Generates end-to-end Playwright TypeScript test scripts from a target URL using a four-agent linear pipeline: Clarifier (collects user story or action sequence from the user), Planner (produces a structured test plan), Generator (writes Playwright TypeScript code via the Playwright MCP tool), and Healer (re-runs failing scripts and auto-heals locator errors). No HITL gates — the pipeline runs to completion and surfaces results as a test plan markdown document, a code viewer, and a test execution report. Approximately 85% of the workflow is autonomous; the user provides a target URL and optionally a user story or description of what to test. The agent requires the Playwright MCP server to be running and accessible.

## Autonomy Level
L4 · Collaborative (~15% human control).

The only user input is the initial `targetUrl` and optional action description. The pipeline runs fully autonomously thereafter — Clarifier may ask one clarifying question before passing to Planner if the scope is ambiguous. The Healer runs up to 3 self-correction rounds on failing scripts before exiting.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Target URL | Yes | The web application URL to generate tests for |
| User Story / Action Sequence | No | Description of the user journey to test; Clarifier derives one from the URL if omitted |
| Project | Yes | Scopes script versioning and MCP server context |

## Outputs
| Output | Description |
|--------|-------------|
| Test Plan | Structured markdown describing the scenarios to be automated |
| Code Viewer | Generated (and healed) Playwright TypeScript test files |
| Test Report | Per-test results from the final script execution, with pass/fail status and error details |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Provide a target URL in the workspace; optionally describe the actions to test |
| API | Submit the target URL and optional user story programmatically |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, Node.js 18+, Playwright MCP server (`@playwright/mcp`), browser binaries (`npx playwright install`).

## Limitations
- Requires the Playwright MCP server to be running and accessible on the configured MCP socket; the Generator agent will fail without it.
- Generated scripts target the exact URL provided; dynamic URLs (SSO-gated, IP-restricted, or ephemeral environments) must be accessible from the agent host.
- The Healer repairs locator errors and element-not-found failures; logical test failures (wrong assertions) require manual correction.
- Self-healing is bounded at 3 rounds per script; persistently failing tests exit with a partial pass/fail report.
