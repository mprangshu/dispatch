---
agent_id: accessibility-auditor
name: Accessibility Auditor Agent
domain: testing
tags: [accessibility, wcag, a11y, audit, remediation]
autonomy_default: L3
autonomy_supported: [L2, L3]
triggers: [manual, webhook]
---

## Overview
The Accessibility Auditor checks a web application against the WCAG 2.2 guidelines
and tells you what to fix. It crawls the pages you point it at, evaluates each
against the success criteria (contrast, alt text, labels, focus order, ARIA
usage), and produces a prioritised report with the offending element and a
concrete remediation for each issue. It can rewrite the suggested markup fixes for
review, helping teams move from "what's wrong" to "here's the fix" quickly.

## Autonomy Level
L3 · Goal-driven with review checkpoints.

The agent runs toward the goal of a WCAG-conformant page set, pausing to let the
user confirm the page scope before crawling and to approve suggested markup fixes
before they are bundled into the remediation output.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Start URL | Yes | The page or site entry point to audit |
| Conformance target | No | WCAG level to test against: A, AA, or AAA (default: AA) |
| Crawl depth | No | How many link levels deep to crawl from the start URL (default: 2) |
| Page allow/deny list | No | Restrict or exclude specific paths from the audit |

## Outputs
| Output | Description |
|--------|-------------|
| Accessibility report | Issues grouped by WCAG success criterion, each with severity, the offending element, and a remediation |
| Remediation snippets | Suggested markup/ARIA fixes for each issue, for human review |
| Conformance scorecard | Pass/fail per criterion and an overall conformance level for the audited pages |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Enter a start URL and conformance target in the workspace |
| Webhook | Automatically re-audit when a deploy webhook fires for the target site |

## Deployment
**Hardware:** 2 vCPU, 4 GB RAM, and ~5 GB free disk for crawl artifacts and screenshots.
**Software:** Linux/Windows host with Python 3.11+, a headless Chromium browser, and outbound network access to the audited site.

## Limitations
- Automated checks cover the machine-testable WCAG criteria; some criteria (e.g. meaningful alt-text quality) still need human judgement.
- Audits web content only; native mobile and PDF documents are out of scope.
- Pages behind complex authentication may require a supplied session to be crawled.
