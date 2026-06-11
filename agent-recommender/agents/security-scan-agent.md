---
agent_id: security-scan-agent
name: Security Scan Agent
domain: testing
tags: [security-testing, sast, dast, vulnerability-scanning, owasp]
autonomy_default: L1
autonomy_supported: [L1, L2]
triggers: [manual, api]
---

## Overview
The Security Scan Agent looks for common vulnerabilities in an application before
release. It runs static analysis (SAST) over a source repository and dynamic
analysis (DAST) against a running URL, mapping findings to the OWASP Top 10. Each
finding includes a severity, the affected location, and a suggested remediation.
Because security findings need human judgement, the agent defaults to a
review-first posture and never changes code on its own.

## Autonomy Level
L1 (default) · Supported: L1, L2.

| Level | Behaviour |
|-------|-----------|
| L1 | Scans and reports; a human triages every finding before any action is taken. |
| L2 | Scans, reports, and auto-files tickets for high/critical findings; remediation stays human-owned. |

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| Repository | Yes (SAST) | The source repo URL/branch to analyse statically |
| Target URL | Yes (DAST) | The running application to scan dynamically |
| Scan profile | No | Quick vs. deep scan; defaults to a balanced profile |
| Exclusions | No | Paths or rules to skip (e.g. third-party vendor directories) |

## Outputs
| Output | Description |
|--------|-------------|
| Findings report | Vulnerabilities with severity, location, OWASP category, and a remediation suggestion |
| Severity summary | Counts by severity (critical/high/medium/low) for a quick gate decision |
| SARIF export | Machine-readable findings for ingestion by code-scanning dashboards |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Provide a repo and/or target URL in the workspace |
| API | Start a scan programmatically via the run endpoint |

## Deployment
**Hardware:** 4 vCPU, 8 GB RAM, and ~15 GB free disk for cloned sources and scan databases.
**Software:** Linux host with Python 3.11+, the bundled SAST/DAST scanners, and outbound network access to the target URL and repository.

## Limitations
- Reports potential vulnerabilities; it does not exploit them or confirm exploitability.
- DAST coverage is limited to areas reachable without complex authenticated workflows.
- Findings require human triage — false positives are expected and the agent never edits code itself.
