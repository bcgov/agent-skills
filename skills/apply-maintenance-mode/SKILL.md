---
name: apply-maintenance-mode
description: 'Automates the transition of a repository into "Maintenance Mode" (Renovate auto-merge, unconditional tests, deployment upgrades). Use only after a repository has passed the github-repo-setup maturity audit.'
owner: bcgov
tags: [maintenance, devops, renovate, github-actions, bcgov]
---

# Apply Maintenance Mode

Automate the scaffolding and configuration required to put a mature BC Gov repository into a hands-off, automated maintenance mode. This enforces zero-review auto-merges for dependencies, provided all CI tests pass.

## Use When
- The user asks to put a specific app, repo, or service into "maintenance mode" or "autopilot".
- You have verified the repository is mature enough (must have a CI test suite).
## Don't Use When
- The repository does not have an automated test suite.
- The user explicitly asks for manual deployment gates.

## Pre-flight Checklist (CRITICAL)

Before making any changes, you **MUST** verify the repository has an automated CI test suite (e.g., checking `.github/workflows/` for testing workflows or inspecting `package.json` for test scripts that run in CI).

- **IF NO TEST SUITE EXISTS**: **HARD-STOP**. Throw an error to the user. Explain that an automated test suite is a hard prerequisite for safe auto-merge. Instruct them to either build tests first or run the `github-repo-setup` audit skill.
- **IF TEST SUITE EXISTS**: Proceed with the steps below.

## Workflow

### 1. Repository API Configuration (GitHub Settings)
Use the `gh` CLI to enable native auto-merge and status checks on the repository:
- Enable Auto-Merge: `gh api -X PATCH repos/{owner}/{repo} -F allow_auto_merge=true`
- Ensure branch protections require the test suite status checks to pass before merging.

### 2. Renovate Configuration
Modify or create `renovate.json` (or `renovate.json5`) at the repository root.
- Ensure the repository inherits from the centralized BC Gov preset: `"extends": ["github>bcgov/renovate-config"]` (or a specific version tag). 
- *Note*: The `bcgov/renovate-config` preset automatically enables `automerge: true` for safe minor and patch updates, so you do not need to add any custom local auto-merge rules.

### 3. CI/CD Deployment Pipeline Upgrades
Analyze `.github/workflows/` and standardize the deployment pipeline. Teams are explicitly moving away from `workflow_dispatch` gates.

- **Legacy Anti-Pattern (`workflow_dispatch`)**: If you detect a `workflow_dispatch` gated PROD deployment, mark it as legacy and **upgrade it to Release-Gated**.
- **Target Pattern 1: Release-Gated**:
  - `TEST` deploys automatically on push to `main`.
  - `PROD` deploys automatically when a GitHub Release is published (`on: release: types: [published]`).
- **Target Pattern 2: Straight-to-TEST+PROD**:
  - `TEST` and `PROD` deploy automatically and sequentially on push to `main`.

Migrate the pipeline to the appropriate target pattern based on the repo's existing behavior or explicit user instruction.

## Rules
- **Kill `workflow_dispatch`**: Under no circumstances should you generate or preserve a `workflow_dispatch` trigger for a production deployment. It is an inconsistent legacy pattern.
- **Always rely on `bcgov/renovate-config`**: Do not write overly verbose, custom Renovate rules locally if the central preset exists.
 
## Examples
- The user asks: "Enable maintenance mode for this repo". You check for tests, then apply auto-merge and Renovate configs.

## Edge Cases
- If the repository has a complex mono-repo setup, ensure branch protections cover all critical path tests.

## References
- `gh` CLI documentation for setting up repository features.
