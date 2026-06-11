---
name: github-repo-setup
description: 'Assess GitHub repository maturity against BC Gov DevOps and security standards. Generates a MATURITY_REPORT.md scorecard covering branch protection rulesets, TypeScript strictness, Renovate preset tracing, vulnerability SLAs, CI/CD quality gates, and OpenShift container security. Use when onboarding repos, running compliance reviews, or evaluating vendor conformance.'
owner: bcgov
tags: [github-repo-setup, devops, security, bcgov, audit, compliance]
---

# GitHub Repository Setup Validation

Evaluate repository compliance against BC Gov DevOps and security standards by inspecting config files, querying GitHub APIs, and generating a structured maturity report.

## Use When
- Onboarding a new repository to a BC Gov GitHub organization.
- Preparing for a security audit, compliance review, or sprint planning.
- Evaluating a repository before transitioning it to maintenance mode.
- Validating vendor compliance with BC Gov digital standards.

## Don't Use When
- Auditing personal, experimental, or toy repositories not bound for a BC Gov environment.
- Reviewing documentation-only or basic scripting repositories that do not deploy software.

## Workflow

1. **Analyze Project Structure** — Walk the repo root and identify: `package.json`, `tsconfig.json`, `renovate.json` or `dependabot.yml`, `.github/workflows/`, OpenShift/Kubernetes manifests, `SECURITY.md`, `.github/ISSUE_TEMPLATE/`.

2. **Inspect Server-side Config** (Dimensions 1–2) — Use `gh api graphql` to query repository settings and branch rulesets. If `gh` CLI is unavailable, mark findings as **Unverified** (distinct from Not Met). See [REFERENCE.md query example](./references/REFERENCE.md#dimension-2-branch-protection-rulesets).

3. **Inspect Code and File-based Config** (Dimensions 3–5, 8–9):
   - Read `tsconfig.json` for `strict: true`; grep for `@ts-ignore`, `@ts-nocheck`, `eslint-disable`.
   - Read `renovate.json` — trace preset inheritance through `extends` entries to determine effective automerge, schedule, and minimumReleaseAge settings.
   - Read `.github/workflows/` for test/coverage/scan gates.
   - Read deployment manifests for `runAsNonRoot`, `readOnlyRootFilesystem`, probes.

4. **Assess Processes and Docs** (Dimensions 6–7) — Read `SECURITY.md` and issue templates for documented triage workflow and SLAs. Read workflows for image promotion patterns.

5. **Draft and Write Report** — Score each of the 9 dimensions (Met / Partial / Not Met / Unverified) using the rubric in [REFERENCE.md](./references/REFERENCE.md#1-scoring-rubric). Calculate compliance percentage, map to Maturity Level 1–5, and generate `MATURITY_REPORT.md` in the audited repo root using the [report template](./references/REFERENCE.md#report-template).

## Rules

All dimension definitions and scoring details are in [REFERENCE.md](./references/REFERENCE.md#2-nine-compliance-dimensions--detailed-rules).

### Nine Compliance Dimensions

- **Dim 1 – Repo Settings**: Squash merging enforced, auto-cleanup, suggest updates. **Requires GitHub API.**
- **Dim 2 – Branch Rulesets**: PR requirement, approvals, linear history, status checks. **Requires `gh api graphql`.**
- **Dim 3 – Code Hygiene**: TS strict mode, linting enforced, no diagnostic escapes, 80%+ test coverage.
- **Dim 4 – Secrets**: Token/password separation per environment, 32+ char passwords.
- **Dim 5 – Dependency Updates**: Renovate/Dependabot configured, BC Gov preset preferred, 7-day minimum release age, automerge enabled. **Trace preset inheritance.**
- **Dim 6 – Vulnerability SLAs**: Documented triage workflow, CISA KEV monitoring, EPSS scoring. Critical 24h / High 1w / Medium 2w / Low next sprint.
- **Dim 7 – CI/CD and Deployments**: PR preview envs, image promotion (no rebuilds), SHA-based image references, health probes.
- **Dim 8 – Quality Gates**: TS/lint/test/coverage/scan failures block merge.
- **Dim 9 – OpenShift Security**: Pod security contexts (runAsNonRoot, readOnlyFS), capabilities dropped, seccomp, probes. For remediation, defer to [openshift-deployment SKILL](../openshift-deployment/SKILL.md).

### Critical Rules

- **No-Exemption Policy**: All security vulnerabilities must be remediated. No exceptions for "trusted environments" or "internal access."
- **Unverified vs Not Met**: When a data source (GitHub API, `gh` CLI) is unavailable, mark as **Unverified** — not "Not Met." Do not fabricate findings.
- **Renovate Preset Tracing**: Trace all `extends` entries, fetch referenced preset repos, merge with local overrides, report effective settings.
- **Cross-Reference**: For OpenShift manifest remediation, defer to [openshift-deployment SKILL](../openshift-deployment/SKILL.md).

## Output Format

Generate `MATURITY_REPORT.md` in the audited repo root using the [report template in REFERENCE.md](./references/REFERENCE.md#report-template).

**Report includes:** Executive Summary (score, level, date), 9-dimension breakdown table, detailed checklist with `[x]`/`[ ]`/`[?]` markers, scoring formula, and prioritized remediation (Tier 1 blocking, Tier 2 recommended, Tier 3 optional).

## Examples

### Example 1: Production Microservice
**Prompt**: "Assess bcgov/my-api-service for compliance"
**Process**: Walk repo → find TypeScript + Renovate + OpenShift manifests → verify `strict: true` → trace Renovate preset inheritance → check pod security contexts → score 85% (gaps: missing PDB, coverage at 78%) → generate report.
**Output**: `MATURITY_REPORT.md` with Level 4 (Managed), 2 Tier-2 remediation items.

### Example 2: New Repository Onboarding
**Prompt**: "Is this repo ready for BC Gov production?"
**Process**: Walk repo → find React app, no `renovate.json`, no branch ruleset → score 55% → flag Tier-1 blockers.
**Output**: `MATURITY_REPORT.md` with Level 3 (Defined), 4 Tier-1 blocking items.

## Edge Cases

- **Monorepos**: Inspect root `tsconfig.json` and workspace-level configs. Flag inconsistencies across packages.
- **Non-TypeScript Repos**: Skip TS-specific rules. Assess language-appropriate linting (ESLint for JS, Pylint for Python).
- **GitHub API Unavailable**: Mark Dims 1–2 as **Unverified**. Example: "Unverified (GitHub API access required). Recommend: `gh auth login` and re-run."
- **Renovate Config Without Extends**: Note default Renovate behavior applies. Verify manual config is comprehensive.
- **Legacy Branch Names** (`master`, `develop`): Audit still applies. Flag as low-priority gap.
- **Exempt Repos**: Documentation-only or archived repos — mark dimensions N/A with documented reason.
- **Reproducibility**: Two runs on the same repo must produce identical scores. Use explicit rubric; mark Unverified rather than guessing.

## References

- [REFERENCE.md](./references/REFERENCE.md) — Scoring rubric, 9 dimension definitions, SLA workflow, image promotion pattern, report template, GraphQL query examples.
- [github-actions SKILL](../github-actions/SKILL.md) — Status check aggregator pattern and CI/CD best practices.
- [openshift-deployment SKILL](../openshift-deployment/SKILL.md) — OpenShift pod security contexts and manifest authoring.
- [BC Gov Renovate Config](https://github.com/bcgov/renovate-config) — Inherited preset configurations.
- [GitHub CLI Reference](https://cli.github.com/manual/gh_api) — `gh api` for GraphQL queries.
- [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities) — Actively exploited CVE tracking.
- [NIST EPSS](https://www.first.org/epss/) — Exploit Prediction Scoring System.
