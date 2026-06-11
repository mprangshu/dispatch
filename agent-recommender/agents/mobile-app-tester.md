---
agent_id: mobile-app-tester
name: Mobile App Tester Agent
domain: testing
tags: [mobile-testing, ios, android, appium, device-farm]
autonomy_default: L2
autonomy_supported: [L1, L2]
triggers: [manual, api]
---

## Overview
The Mobile App Tester runs functional tests against native iOS and Android apps.
You upload a build (`.apk` or `.ipa`) and describe the flows you want covered; the
agent installs the app on emulators or a device farm, drives the UI through
Appium, and verifies each flow. It captures device logs and screenshots on
failure and returns a per-device report, so teams can confirm a build works across
OS versions and form factors before release.

## Autonomy Level
L2 (default) · Supported: L1, L2.

| Level | Behaviour |
|-------|-----------|
| L1 | Proposes the flows and the device matrix; the user approves before any run. |
| L2 | Provisions devices, runs the flows, and reports automatically; the user reviews results. |

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| App build | Yes | The `.apk` (Android) or `.ipa` (iOS) to install and test |
| Flow description | Yes | The user journeys to cover (e.g. sign-up, checkout) |
| Device matrix | No | OS versions / device types to run against (default: latest two OS versions) |
| Test account | No | Credentials for flows that require a signed-in user |

## Outputs
| Output | Description |
|--------|-------------|
| Per-device report | Pass/fail for each flow on each device, with a final status per device |
| Failure artifacts | Screenshots and device logs captured at the point of failure |
| Flow coverage summary | Which described flows were exercised and which were skipped |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Upload a build and describe the flows in the workspace |
| API | Submit a build for testing programmatically via the run endpoint |

## Deployment
**Hardware:** 4 vCPU, 8 GB RAM, and ~20 GB free disk for emulator images and build artifacts; access to a device farm is recommended for real-device coverage.
**Software:** Linux/macOS host with Python 3.11+, Appium, and the Android SDK / Xcode toolchain (or a cloud device-farm endpoint).

## Limitations
- Covers native iOS/Android apps; mobile web is better served by the Test Script Generator Agent.
- Real-device coverage depends on device-farm availability; without it, runs are limited to emulators.
- Cannot test flows that depend on hardware unavailable to emulators (e.g. NFC, biometrics) unless run on a capable physical device.
