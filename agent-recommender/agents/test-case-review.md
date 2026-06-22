---
agent_id: test-case-review
name: Test Case Review
domain: testing
tags: [test-case, review, quality-gate, coverage, duplicate-detection, correctness]
autonomy_default: L2
autonomy_supported: [L2]
triggers: [manual, api]
---

## Overview
Reviews a set of test cases for quality, completeness, and redundancy. Given test cases for a user story or module, the agent checks correctness (alignment with acceptance criteria), detects near-duplicate or overlapping scenarios, and identifies coverage gaps against the stated requirements. It produces a structured review report with actionable recommendations — flagging each test case as approved, needs-revision, or duplicate, and listing missing scenarios. This agent is in the design phase; implementation is pending detailed specification.

## Autonomy Level
L2 · Supervised.

The agent presents its review findings at a HITL checkpoint before publishing. The user can accept, dismiss, or override individual flags before the final report is saved.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Test Cases | Yes | The test cases to review (from the project's test suite or provided directly) |
| User Story / Requirements | Yes | Acceptance criteria or requirements to check coverage against |
| Project | Yes | Scopes retrieval of related test cases and requirements context |

## Outputs
| Output | Description |
|--------|-------------|
| Review Report | Per-test-case verdict (approved / needs-revision / duplicate) with rationale |
| Coverage Gap List | Scenarios missing from the test set relative to the stated requirements |
| Recommendations | Specific suggestions for test cases that need revision |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Provide test cases and requirements in the workspace |
| API | Submit test case IDs and requirement references programmatically |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, outbound LLM access.

## Limitations
- Implementation is pending; this catalog entry describes the intended design and may change before release.
- Duplicate detection uses semantic similarity; near-identical test cases with different data values may not be flagged.
- Coverage gap analysis is bounded by the quality of the requirements input; vague or incomplete acceptance criteria reduce gap-detection accuracy.
