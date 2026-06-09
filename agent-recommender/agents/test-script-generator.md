---
agent_id: test-script-generator
name: Test Script Generator Agent
domain: testing
tags: [ui-automation, test-scripts, browser, self-healing, test-report]
autonomy_default: L4
autonomy_supported: [L4]
triggers: [manual]
---

## Overview
The Test Script Generator takes a live application URL and produces ready-to-run UI
automation test scripts. You describe what you want to test — or upload your existing
manual test cases — and the agent opens a real browser, explores the application,
writes the test scripts, runs them, and automatically fixes any failures before
delivering the final output.

## Autonomy Level
L4 · Collaborative (~15% human control).

The agent drives the full explore → write → run → heal cycle on its own, with only a
small amount of human control.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Target URL | Yes | The live application URL the agent opens and tests against |
| Description | No | Describe the features or user flows you want automated |
| Test Cases File | No | Upload an Excel (.xlsx) or CSV file of pre-written manual test cases — the agent automates every scenario in it |
| Max Heal Attempts | No | How many fix-and-retry cycles to run if tests fail (default: 3) |

> Only the Target URL is required. If you upload test cases without a description,
> the agent works from the file content alone.

## Outputs
| Output | Description |
|--------|-------------|
| Test Plan | A structured document describing which flows will be tested, the steps, and expected outcomes — produced before any scripts are written |
| Test Scripts | Automation test files ready to run, one per scenario group (or a single file if requested) |
| Test Report | Pass/fail results per test across all heal attempts, with screenshots and a final status: pass / partial / fail |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Provide a URL and description directly in the workspace |

## Deployment
**Hardware:** TBD
**Software:** TBD

## Limitations
Not specified in source.
