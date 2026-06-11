---
name: github-repo-setup
description: "Audit GitHub repository compliance: maturity scorecard, conformance to BC Gov DevOps & security standards, TypeScript strictness, Renovate preset tracing, container security posture. Generates reproducible MATURITY_REPORT.md. Use when onboarding repos, compliance reviews, or evaluating vendor conformance."
owner: bcgov
tags: [github-repo-setup, devops, security, bcgov, audit, compliance, maturity, scorecard]
---

# GitHub Repository Setup Validation

Evaluate repository compliance against contractually mandated BC Gov DevOps and security standards by reading config files, running commands, and generating a detailed executive compliance report (`MATURITY_REPORT.md`).

## Use When
- Onboarding a new repository to a BC Gov GitHub organization.
- Preparing for a security audit, compliance review, or sprint planning.
- Evaluating a repository before transitioning it to maintenance mode.
- Validating vendor compliance with BC Gov digital standards.

## Don't Use When
- Auditing personal, experimental, or toy repositories not bound for a BC Gov environment.
- Reviewing documentation-only or basic scripting repositories that do not deploy software.

## Workflow

The audit follows a 5-step inspection process mapped to the 9 compliance dimensions (see [references/REFERENCE.md](./references/REFERENCE.md) for detailed definitions):

1. **Analyze Project Structure** (Dims 1–2, 5, 7–9)
   - Walk repo root; list: `package.json`, `tsconfig.json`, `renovate.json`, `.github/workflows/`, OpenShift/Kubernetes manifests, `.github/ISSUE_TEMPLATE/`, SECURITY.md

2. **Inspect Server-side Config via GitHub API** (Dims 1–2)
   - **Dimension 1** (Repo Settings): Use `gh api graphql` or GitHub web UI (Settings → General) to verify squash merge, auto-cleanup, suggest updates
   - **Dimension 2** (Branch Rulesets): Query `repository.rulesets` for `main` branch; verify rule types (`PULL_REQUEST`, `REQUIRED_STATUS_CHECKS`, `NON_FAST_FORWARD`), enforcement = `ACTIVE`
   - **If gh CLI unavailable**: **Stop and ask user** to manually verify or note as **Unverified** (distinct from Not Met). See [references/REFERENCE.md](./references/REFERENCE.md#2-branch-protection-rulesets) for query example.

3. **Inspect Code & File-based Config** (Dims 3–5, 8–9)
   - **Dimension 3** (Code Hygiene): Read `tsconfig.json` (strict: true?); grep for `@ts-ignore`, `@ts-nocheck`, `eslint-disable`; measure test coverage
   - **Dimension 4** (Secrets): Review SECURITY.md, workflow config for token/password separation per environment
   - **Dimension 5** (Dependency Updates): Read `renovate.json` or `dependabot.yml`; **trace Renovate preset inheritance** to verify effective settings (automerge, schedule, minimumReleaseAge)
   - **Dimension 8** (Quality Gates): Read `.github/workflows/` for test/coverage/scan gate failures
   - **Dimension 9** (OpenShift Security): Read `*.deploy.yml` manifests; verify `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, startup/readiness/liveness probes

4. **Assess Processes & Docs** (Dims 6–7)
   - **Dimension 6** (Vulnerability SLAs): Read `.github/ISSUE_TEMPLATE/security-*.md`, SECURITY.md for documented triage workflow; check for CISA KEV / EPSS mentions (see [REFERENCE.md SLA workflow](./references/REFERENCE.md#3-vulnerability-sla-response-workflow))
   - **Dimension 7** (CI/CD & Deployments): Read workflow files for PR preview env deployment, image SHA promotion pattern; check manifests for health probes (see [REFERENCE.md image promotion](./references/REFERENCE.md#4-image-promotion-workflow-definition))

5. **Draft & Write Report**
   - Score each dimension (Met / Partial / Not Met / Unverified) using rubric in [references/REFERENCE.md](./references/REFERENCE.md#1-scoring-rubric)
   - Calculate overall compliance % (equal-weight dimensions, exclude N/A from denominator)
   - Map % to Maturity Level 1–5
   - Generate `MATURITY_REPORT.md` in repo root using [REPORT_TEMPLATE.md](./resources/REPORT_TEMPLATE.md)
   - Include specific remediation items (Tier 1: blocking, Tier 2: recommended, Tier 3: optional)

## Rules

All compliance rules are defined in detail in [references/REFERENCE.md](./references/REFERENCE.md#2-nine-compliance-dimensions--detailed-rules).

### Summary & Quick Reference

- **Dimension 1 – Repo Settings**: Squash merging, auto-cleanup, suggest updates; **query via GitHub API**
- **Dimension 2 – Branch Rulesets**: PR requirement, approvals, linear history, status checks; **query via `gh api graphql rulesets`**; mark **Unverified** if API unavailable
- **Dimension 3 – Code Hygiene**: TS strict mode, linting enforced, no diagnostic escapes, 80%+ test coverage
- **Dimension 4 – Secrets**: Token/password separation per environment, 32+ char passwords
- **Dimension 5 – Dependency Updates**: Renovate/Dependabot, BC Gov preset preferred, 7-day minimum release age, automerge enabled; **trace preset inheritance** to verify effective settings
- **Dimension 6 – Vulnerability SLAs**: Documented triage workflow, CISA KEV monitoring, EPSS scoring; Critical (24h) / High (1w) / Medium (2w) / Low (next sprint)
- **Dimension 7 – CI/CD & Deployments**: PR preview envs, image promotion (no rebuilds), SHA-based image references, startup/readiness/liveness probes
- **Dimension 8 – Quality Gates**: TS/lint/test/coverage/scan failures block merge
- **Dimension 9 – OpenShift Security**: Pod security contexts (runAsNonRoot, readOnlyFS), capabilities dropped, seccomp runtime default, health probes; for remediation, see [openshift-deployment SKILL](../openshift-deployment/SKILL.md)

### Critical Definitions

- **No-Exemption Policy**: All security vulnerabilities must be remediated regardless of justifications like "trusted environments," "internal access," or "unreachable paths."
- **GitHub API Requirement for Dims 1–2**: Repository settings and branch rulesets are server-side config. Use `gh api graphql` or GitHub web UI. If unavailable, mark as **Unverified** (not "Not Met").
- **Unverified State**: Distinct from "Not Met". Use when data source (GitHub API, gh CLI, etc.) is unavailable. Do not fabricate findings.
- **Renovate Preset Tracing**: When assessing Renovate configuration, trace all inherited presets to determine effective settings:
  1. Identify all `extends` entries in `renovate.json` (local and extended configs).
  2. For `github>org/repo#version` presets, fetch the referenced repository version and read its config files.
  3. Merge local overrides with inherited settings using Renovate's precedence rules (local > later extends > earlier extends).
  4. Report the **effective settings** for automerge, schedule, minimumReleaseAge, dependency grouping rules.
  5. Flag conflicts or overrides that weaken security or automation posture.
- **Cross-Reference**: For OpenShift remediation & manifest authoring, defer to [openshift-deployment SKILL](../openshift-deployment/SKILL.md) (canonical source)

## Output Format

Generate `MATURITY_REPORT.md` in the audited repository root following [REPORT_TEMPLATE.md](./resources/REPORT_TEMPLATE.md).

**Report Structure:**
- **Executive Summary**: Score, Maturity Level (1–5), assessment date
- **Dimension Breakdown**: 9-row table (Met / Partial / Not Met / Unverified) with findings
- **Detailed Checklist**: Checkbox format per dimension; mark items `[x]` or `[ ]` or `[?]` (Unverified)
- **Scoring Rubric**: Reference [REFERENCE.md](./references/REFERENCE.md#1-scoring-rubric) formula; note any weighting applied
- **Key Actions Required**: Prioritized by Tier (Tier 1: blocking, Tier 2: recommended, Tier 3: optional)
- **Compliance Summary**: High-level table of status per category
- **Next Review Date**: Typically 30 days after report generation

## Examples

### Example 1: Assessment of a Production Microservice
**Input**: Repository URL: `bcgov/my-api-service`  
**Process**:
1. Walk repository: Find `package.json` with TypeScript, `tsconfig.json`, `renovate.json`, `.github/workflows/`, and `openshift.deploy.yml`.
2. Check TypeScript strictness: Verify `strict: true` in `tsconfig.json`.
3. Run `npm audit` and check for bypasses (`@ts-ignore`, `eslint-disable`).
4. Inspect Renovate config: Local `renovate.json` extends `github>bcgov/renovate-config#2026.04`. Fetch inherited preset and verify effective automerge, schedule, and minimumReleaseAge.
5. Examine OpenShift manifest: Confirm `readOnlyRootFilesystem: true`, `runAsNonRoot: true` in security contexts.
6. Draft scorecard: 85/100 (gaps: missing PodDisruptionBudget, test coverage at 78%).
7. Write report: Generate `MATURITY_REPORT.md` with actionable remediation items.

**Output**: `MATURITY_REPORT.md` with 9-dimension compliance checklist and Renovate inheritance analysis.

### Example 2: Onboarding a New Repository
**Input**: Repository URL: `bcgov/experimental-frontend`  
**Process**:
1. Analyze structure: Find React app with Jest tests, but missing `renovate.json`.
2. Check TypeScript: `tsconfig.json` lacks strict mode settings.
3. Inspect branch protection: No ruleset on `main` branch.
4. Assess GitHub settings: Merge/rebase commits enabled (should be squash-only).
5. Draft scorecard: 60/100 (high-priority gaps: branch protection, Renovate, TypeScript strictness).
6. Write report with 5–7 remediation items.

**Output**: `MATURITY_REPORT.md` with clear Tier 1 (blocking) and Tier 2 (recommended) actions.

## Edge Cases

- **Monorepos with Multiple `tsconfig.json` Files**: Inspect root `tsconfig.json` and any workspace-level configurations. Flag inconsistencies in strictness across packages.
- **Renovate Config Missing Extends**: If `renovate.json` exists but has no `extends`, note that default Renovate behavior applies (no inherited presets). Verify manual configuration is comprehensive.
- **GitHub API Unavailable** (Dims 1–2): If `gh` CLI or GitHub web access is unavailable, mark server-side findings as **Unverified** (not "Not Met"). Example: "⚠️ Unverified (GitHub API access required). Recommend: `gh auth login` and re-run."
- **Non-TypeScript Repositories**: Skip TypeScript-specific rules (strict mode, `@ts-ignore`). Assess applicable language-specific linting (ESLint for JavaScript, Pylint for Python, etc.).
- **Legacy Branch Names (`master`, `develop`)**: Audit still applies. Flag as a low-priority gap if org standards require `main`.
- **Exempt Repositories**: Documentation-only, archived, or experimental repositories should be marked N/A. Document the reason in the report.
- **Reproducibility**: Two audit runs on the same repo should produce identical scores. Use explicit rubric (equal-weight dimensions, N/A handling). If API unavailable, mark Unverified rather than fabricating data.

## References

- [references/REFERENCE.md](./references/REFERENCE.md) – Complete scoring rubric, nine dimension definitions, SLA workflow, image promotion pattern, EPSS guidance, Unverified state definition, GraphQL query examples.
- [REPORT_TEMPLATE.md](./resources/REPORT_TEMPLATE.md) – Report template for compliance scorecards.
- [github-actions SKILL](../github-actions/SKILL.md) – Canonical source for status check aggregator pattern and CI/CD best practices.
- [openshift-deployment SKILL](../openshift-deployment/SKILL.md) – Canonical source for OpenShift pod security contexts and manifest authoring.
- [BC Gov Renovate Config](https://github.com/bcgov/renovate-config) – Inherited preset configurations for dependency updates.
- [GitHub CLI Reference](https://cli.github.com/manual/gh_api) – `gh api` for GraphQL queries; rulesets API documentation.
- [GitHub GraphQL API - Repository Rulesets](https://docs.github.com/en/graphql/reference/objects#repository) – Query `rulesets` for branch protection configuration.
- [CISA Known Exploited Vulnerabilities (KEV)](https://www.cisa.gov/known-exploited-vulnerabilities) – Actively exploited CVE tracking.
- [NIST EPSS](https://www.first.org/epss/) – Exploit Prediction Scoring System for vulnerability prioritization.
