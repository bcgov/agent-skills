---
name: github-repo-setup
description: Assess GitHub repository and application maturity against BC Gov DevOps & Dependency Security Standards, including mandatory branch protection, TypeScript settings, and container security. Writes a structured compliance report.
owner: bcgov
tags: [github-repo-setup, devops, security, bcgov]
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
1. **Analyze Project Structure**: Walk the repository root and list configuration files (`package.json`, `tsconfig.json`, `renovate.json`, `.github/workflows/`, and OpenShift/kubernetes manifests).
2. **Inspect Files & Run Commands**: Auditing agent must directly examine code files and execute CLI tools where available:
   - Check `tsconfig.json` for strict TypeScript compiler options.
   - Run `npm audit` or security checks if dependencies need audit verification.
   - Search the codebase using grep to detect any diagnostic bypasses (`@ts-ignore`, `eslint-disable`).
   - Read workflow files under `.github/workflows/` to verify CI/CD pipelines fail on warnings and test coverage gates are enforced.
   - Look at OpenShift deployment templates/manifests to verify security contexts (`runAsNonRoot: true`, `readOnlyRootFilesystem: true`).
   - **Trace Renovate configuration inheritance**: If `renovate.json` extends presets (e.g., `github>bcgov/renovate-config`), fetch and analyze the inherited configuration files to determine effective settings, particularly `automerge`, `schedule`, and `minimumReleaseAge`.
3. **Assess Repo configuration (GitHub API/Git)**:
   - Check local git configurations and repository parameters when querying. If online API tools are unavailable, perform manual reasoning on branch naming, rulesets, and pull requests.
4. **Draft the Compliance Scorecard**:
   - Compare the findings against the [BCGov DevOps & Dependency Security Standards](https://github.com/bcgov/agent-skills/blob/main/TEAM_CHECKLIST.md) (or `TEAM_CHECKLIST.md`).
   - Use the reference template `skills/github-repo-setup/resources/REPORT_TEMPLATE.md` as the format.
5. **Write Report**: Generate `MATURITY_REPORT.md` in the target repository's root directory. The report must be thorough, precise, and state clear, actionable remediation items.

## Rules
- **No-Exemption Policy**: All security vulnerabilities must be remediated regardless of justifications like "trusted environments," "internal access," or "unreachable paths."
- **GitHub Repository Settings**: Enforce Squash Merging Only (uncheck merge/rebase commits). Enable Branch Auto-Cleanup and Always Suggest Updating PR branches.
- **Branch Protection Ruleset**: The `main` branch ruleset must require a PR, at least 1 approval, conversation resolution, linear history, and strict status checks (`Analysis Results`, `PR Results`, `Validate Results`). Block force pushes.
- **TypeScript Hygiene**: For TypeScript projects, compiler options must enforce strictness:
   ```json
   {
     "compilerOptions": {
       "strict": true,
       "noImplicitAny": true,
       "strictNullChecks": true
     }
   }
   ```
- **Linter & Diagnostic Escapes**: Use of `@ts-ignore`, `@ts-nocheck`, `any` type escapes, or `eslint-disable` is strictly prohibited. Linter warnings or TS compiler diagnostics must fail build pipelines.
- **Test Coverage Baseline**: Maintain a minimum of 80% statement and branch test coverage. PRs that lower coverage below this threshold must be rejected.
- **Dependency Management & Automation**:
  - Automated dependency updates must be enabled via **Renovate** or **Dependabot**.
  - **Renovate** is strongly preferred and scores higher if it extends an upstream BC Gov configuration (e.g., extending `github>bcgov/renovate-config` or using rules similar to `bcgov/copilot-instructions`).
  - **Renovate Preset Tracing**: When assessing Renovate configuration, trace all inherited presets to determine the effective configuration:
    1. Identify all `extends` entries in `renovate.json` (local and in any extended configs).
    2. For `github>org/repo#version` presets, fetch the referenced repository version and read its config files.
    3. Merge local overrides with inherited settings using Renovate's precedence rules (local > later extends > earlier extends).
    4. Report the **effective settings** for automerge, schedule, minimumReleaseAge, and dependency grouping rules.
    5. Flag conflicts or overrides that may weaken security or automation posture.
  - Minimum release age of 7 days before adopting dependency updates.
  - Zero-dependency policy for low-volume (< 20 lines) custom logic.
- **OpenShift Security Context**: Default security contexts (`readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`) must not be bypassed or removed. Write operations must use memory-backed `emptyDir` volumes.
- **Vulnerability SLAs**: Critical findings (24 hours), High (1 week), Medium (2 weeks), Low (next sprint).

## Output Format
Always generate a `MATURITY_REPORT.md` file in the root of the audited repository following the schema defined in `resources/REPORT_TEMPLATE.md`. Ensure that check boxes are marked with `[x]` (Met) or `[ ]` (Not Met/Missing) and a clear, descriptive breakdown of recommendations is presented.