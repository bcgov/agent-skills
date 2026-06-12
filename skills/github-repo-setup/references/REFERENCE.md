# GitHub Repository Setup — Reference & Detailed Guidance

## 1. Scoring Rubric

### How Compliance Score is Calculated

**Formula:**
```
Compliance Score (%) = (Sum of Weighted Dimension Scores / Total Scored Dimensions) × 100
```

**Dimension Point Values:**
- **Met** (`[x]`): 1.0 points. All checks for the dimension pass; zero exceptions or waivers.
- **Partial** (`[~]`): 0.5 points. Deterministic rule: at least one check passes, and at least one check fails.
- **Not Met** (`[ ]`): 0.0 points. All checks fail, or the dimension is fundamentally absent.
- **Unverified** (`[?]`): Excluded from both numerator and denominator (not counted as a failure; data source was unavailable).
- **Not Applicable (N/A)** (`[-]`): Excluded from both numerator and denominator (applies to documentation-only or basic scripting repos where specific dimensions do not apply).

### N/A Handling

- **Excludes from denominator**: N/A dimensions do not reduce the score.
  - Example: If a documentation-only repo marks "CI/CD & Deployments" as N/A, the score is calculated over 8 dimensions: `Score = (7 Met / 8 Scorable) × 100 = 87.5%`.
- **Document the reason**: Always note why N/A is applied in the report's findings (using the `[-]` marker).

### Dimension Weighting

By default, all 9 dimensions are equally weighted (1.0 each) with 2x weighting turned OFF. 

**Conditional Weighting**: 2x weighting is only applied if explicitly specified by organization policy via a config file or user prompt input.
- Dimension 2 (Branch Protection Rulesets) — enforces CI/CD gates (weight 2.0)
- Dimension 6 (Vulnerability SLAs) — enforces security response (weight 2.0)

If 2x weighting is active, the agent must report both the default equally-weighted score and the weighted score. Example weighted calculation:
```
Score = [(7 × 1.0 + 1 × 2.0 + 1 × 2.0) / (8 × 1.0 + 1 × 2.0 + 1 × 2.0)] × 100 = 87%
```

### Maturity Level Mapping

| Compliance Score | Level | Name | Interpretation |
| :---: | :---: | :--- | :--- |
| < 25% | **1** | Initial | Minimal controls; multiple critical gaps |
| 25–49% | **2** | Developing | Basic controls in place; major work needed |
| 50–74% | **3** | Defined | Most controls met; some gaps on specialized areas |
| 75–89% | **4** | Managed | Controls mature; minor hardening needed |
| ≥ 90% | **5** | Optimizing | Controls comprehensive; continuous improvement focus |

---

## 2. Nine Compliance Dimensions — Detailed Rules

### Dimension 1: GitHub Repository Configuration

**Server-side settings** (query via GitHub API / `gh` CLI; cannot be read from repo files).

**Required Data Source:** Use `gh api graphql` or GitHub web UI (Settings → General).

**Checks:**
- [ ] **Squash Merging Enforced**: Merge method = "Squash and merge" only; disable "Allow merge commits" and "Allow rebase merging"
- [ ] **Branch Auto-Cleanup Enabled**: Settings → "Automatically delete head branches" = ON
- [ ] **Suggest Updates Enabled**: Settings → "Always suggest updating pull request branches" = ON
- [ ] **Public Packages (If Applicable)**: Package visibility appropriate for open-source (publish to npm/Maven/PyPI) or internal-only for closed repos

**Rationale:** Squash merging keeps commit history clean; auto-cleanup prevents orphaned branches; suggest updates prevents stale PRs.

**Unverified Marker:** If GitHub API unavailable, note "Unverified (API access required)" rather than "Not Met."

---

### Dimension 2: Branch Protection Rulesets

**Server-side settings** (query via GitHub API / `gh` CLI using `rulesets` query).

**Required Data Source:** Use `gh api graphql` to query `repository.rulesets` for `pattern: "main"` or `pattern: "main*"`.

**Checks:**
- [ ] **Target Branch Protection Active**: Ruleset for `main` exists with `enforcement: ACTIVE`
- [ ] **Pull Request Requirement**: Rule type `PULL_REQUEST` present (requires PR before merge)
- [ ] **Approval Requirement**: Rule includes reviewer approval requirement (typically part of `PULL_REQUEST` rule)
- [ ] **Conversation Resolution**: Rule requires all conversations resolved before merge
- [ ] **Linear History Enforcement**: Rule type `NON_FAST_FORWARD` or equivalent present (prevents merge commits)
- [ ] **Status Checks Required**: Rule type `REQUIRED_STATUS_CHECKS` present; points to a single aggregated results check (per [github-actions SKILL](../../github-actions/SKILL.md)), not individual checks
- [ ] **Force Pushes Blocked**: Rule includes force push restriction (part of `NON_FAST_FORWARD`)
- [ ] **Bypass Restrictions**: Only repository admins bypass allowed; enforce for all other users

**Rationale:** Rulesets prevent accidental/malicious commits, enforce CI/CD gates, and maintain linear history for debuggability.

**Unverified Marker:** If GitHub API/`gh` unavailable, note "Unverified (API access required)" rather than "Not Met."

**API Query Example:**
```bash
gh api graphql -f query='query { 
  repository(owner:"bcgov", name:"REPO") { 
    rulesets(first:10) { 
      edges { 
        node { 
          name 
          target
          enforcement
          rules(first:10) { edges { node { type } } }
        } 
      } 
    } 
  } 
}'
```

---

### Dimension 3: Language & Code Hygiene

**Code-level configuration** (read from repo: `tsconfig.json`, ESLint config, test config).

**Checks:**
- [ ] **TypeScript / Strict Compilation** (If TS project):
  - `"strict": true` in `tsconfig.json`
  - `"noImplicitAny": true`, `"strictNullChecks": true`
  - Additional strictness flags: `"noUncheckedIndexedAccess"`, `"noImplicitThis"`
- [ ] **Linting Configured & Enforced**: ESLint / Pylint / Rubocop configured; fails CI on warnings
- [ ] **No Diagnostic Escapes**: Zero instances of `@ts-ignore`, `@ts-nocheck`, `eslint-disable`, `any` type escapes in source code (generated files exempt)
- [ ] **Test Coverage Baseline (80%+)**: Measured statement + branch coverage ≥ 80%; CI enforces gate
- [ ] **Zero-Dependency Policy**: No low-volume utility functions (< 20 LOC) depend on external packages
- [ ] **No Centralized Dependency Exceptions**: Security scanning (npm audit, pip audit) has zero high-severity exceptions

**Rationale:** Strict mode catches bugs at compile time; linting enforces standards; test coverage ensures logic is exercised; zero-dependency policy reduces supply-chain risk.

---

### Dimension 4: OpenShift & Environment Secrets

**Deployment & secret management** (read from repo: OpenShift manifests, `.github/workflows/`, documentation).

**Checks:**
- [ ] **Service Tokens Separation**: Database, API, and monitoring services use distinct tokens per environment (never shared)
- [ ] **Unique Passwords Across Environments**: Dev, staging, and production use separate credential sets (never reused)
- [ ] **Password Strength**: Minimum 32 random characters (no dictionary words, predictable patterns); meet or exceed NIST guidance

**Rationale:** Token/password separation limits blast radius if one environment is compromised; strong passwords resist brute-force; per-environment secrets prevent cross-env lateral movement.

**Note:** This dimension audits secret *management practices*, not the actual secrets (which cannot be inspected). Verify via documentation, workflow setup, and OpenShift RoleBindings.

---

### Dimension 5: Dependency Update Automation

**Dependency management** (read from repo: `renovate.json`, `dependabot.yml`, workflow configs).

**Checks:**
- [ ] **Renovate or Dependabot Configured**: At least one tool present and active
- [ ] **BC Gov Preset Extended (If Renovate)**: Extends `github>bcgov/renovate-config` or similar upstream BC Gov configuration
- [ ] **Minimum Release Age (7 days)**: Enforced; dependency updates wait ≥ 7 days before adoption
- [ ] **Automerge Enabled**: Non-major updates merge automatically; major updates require manual approval
- [ ] **Dependency Dashboard Active**: Renovate dashboard or Dependabot alerts accessible; team monitors updates
- [ ] **Preset Inheritance Traced**: For extended presets, agent verifies effective settings (automerge, schedule, minimumReleaseAge) by fetching inherited config

**Rationale:** Automated updates reduce manual work; 7-day wait buffers against new CVEs; automerge for patch/minor reduces review fatigue; inherited preset tracing ensures effective config is understood.

---

### Dimension 6: Vulnerability SLAs & Triage

**Vulnerability response process** (read from repo: documentation, issue templates, workflow config).

**Checks:**
- [ ] **Documented Triage Workflow**: GitHub issue template or security policy defines response process (who responds, escalation, remediation timeline)
- [ ] **CISA KEV Monitoring**: Repository subscribes to CISA Known Exploited Vulnerabilities list; flagged vulns trigger immediate response
- [ ] **FIRST EPSS Scoring Integration**: Vulnerabilities triaged by EPSS score when available (Exploit Prediction Scoring System; prioritizes exploitability)
- [ ] **SLAs Enforced**:
  - [ ] **Critical** (CVSS 9.0–10.0 or CISA KEV): Fix within 24 hours or accept risk in writing
  - [ ] **High** (CVSS 7.0–8.9): Fix within 1 week or document exception
  - [ ] **Medium** (CVSS 4.0–6.9): Fix within 2 weeks or schedule for next sprint
  - [ ] **Low** (CVSS 0.0–3.9): Fix in next scheduled release

**Rationale:** SLAs enforce consistent security response; CISA KEV escalates actively-exploited vulns; EPSS prioritizes by exploitability, not just severity; documented workflow ensures accountability.

**Data Source:** Issue template in `.github/ISSUE_TEMPLATE/`, SECURITY.md, or project README.

---

### Dimension 7: CI/CD & Deployments

**Deployment pipeline** (read from repo: `.github/workflows/`, deployment manifests).

**Checks:**
- [ ] **PR-based Preview/Sandbox Deployments**: Workflow spins up preview environment on PR open; torn down on close
- [ ] **Image Promotion Workflow**: Container images built once in CI, then promoted through dev → staging → prod (no rebuild of same code)
- [ ] **SHA-based Image References**: Deployments reference immutable image SHAs, not floating tags (e.g., `image@sha256:abc123...` not `image:latest`)
- [ ] **Deployment Health Gating**: Workflow enforces rollout success gating or traffic routing checks before promoting images (manifest-level probe configurations are scored under Dimension 9, not here. Do not double-count).

**Rationale:** Preview envs reduce integration risk; image promotion ensures audit trail (same artifact → all envs); SHA pinning prevents tag hijack; deployment health gating checks prevent premature routing switch. If unique stable tags (e.g., git commit SHAs, PR numbers) are used instead of digests, score the check as **Partial** (not Met), as they prevent general tag mix-ups but still fail registry-level immutability checks.


**Data Source:** `.github/workflows/` files and OpenShift/Kubernetes manifests (e.g., `*.deploy.yml`).

---

### Dimension 8: CI-Enforced Quality Gates

**Build pipeline enforcement** (read from repo: `.github/workflows/`, CI config).

**Checks:**
- [ ] **TypeScript / Linting Failures Block Merge**: Workflow exits non-zero on TS errors or linting warnings
- [ ] **Test Failures Block Merge**: CI exits non-zero if tests fail
- [ ] **Test Coverage Gate Enforced**: CI fails if coverage drops below 80% threshold
- [ ] **Transitive Dependency Budgeting**: `npm audit --production` or equivalent runs; high/critical vulns block merge
- [ ] **Security Scans Block Merge**: Trivy, SonarCloud, or SAST tool failures prevent merge (Note: This check refers to filesystem/repository scans, secret detection, or static code scanners. Container image-mode scans are optional and must NOT dock points.)


**Rationale:** Automated gates prevent broken code and unvetted dependencies from reaching prod; gates are objective and enforce consistently.

---

### Dimension 9: OpenShift Security Contexts

**Pod security configuration** (read from repo: OpenShift/Kubernetes manifests).

**Checks:**
- [ ] **Pod Security Context (`runAsNonRoot: true`)**: All containers run as non-root user
- [ ] **Pod Security Context (`readOnlyRootFilesystem: true`)**: Root filesystem is read-only; write operations use `emptyDir` volumes
- [ ] **Pod Security Context (`allowPrivilegeEscalation: false`)**: Containers cannot escalate privileges
- [ ] **Capabilities Dropped**: All Linux capabilities dropped (`capabilities: drop: ["ALL"]`)
- [ ] **seccomp Profile**: Runtime security profile enforced (`seccompProfile.type: RuntimeDefault`)
- [ ] **Startup / Readiness / Liveness Probes**: All three probe types configured; startup grace period sized generously per openshift-deployment skill sizing guidance (e.g., failureThreshold × periodSeconds) to prevent premature liveness failure during slow initialization.

**Rationale:** Pod security contexts limit container blast radius; dropped capabilities reduce syscall surface; probes detect and restart unhealthy Pods.

**Cross-Reference:** For remediation and manifest authoring, see [openshift-deployment SKILL](../../openshift-deployment/SKILL.md) (canonical source for security context configuration).

---

## 3. Vulnerability SLA Response Workflow

**CISA KEV & EPSS Triage Decision Tree:**

```
1. Vulnerability discovered (via npm audit, Trivy, SonarCloud, etc.)
   ↓
2. Is it on CISA Known Exploited Vulnerabilities (KEV) list?
   ├─ YES → Escalate to Critical; fix within 24 hours
   └─ NO → Check CVSS & EPSS score (next step)
   ↓
3. Determine CVSS score; if available, also check EPSS (exploitability score 0–1)
   ├─ CVSS 9.0–10.0 or EPSS > 0.8 → Critical (24h SLA)
   ├─ CVSS 7.0–8.9 or EPSS 0.5–0.8 → High (1w SLA)
   ├─ CVSS 4.0–6.9 or EPSS 0.1–0.5 → Medium (2w SLA)
   └─ CVSS 0.0–3.9 or EPSS < 0.1 → Low (next scheduled release SLA)
   ↓
4. Create GitHub issue with template:
   - Title: "[SECURITY] ${CVE-ID}: ${package}@${version} — ${CVSS} ${SLA}"
   - Labels: "security", "cvss-${level}", "cisa-kev" (if applicable)
   - Assignee: On-call security contact
   - Deadline: Based on SLA (24h → 1w → 2w → next scheduled release)
   ↓
5. Remediation:
   - Upgrade to patched version, or
   - Apply backport patch, or
   - Accept risk in writing (document exception in README / SECURITY.md)
   ↓
6. Verification: Re-run audit tool; confirm vuln resolved or exception documented
```

**EPSS Integration:**

- EPSS score available at [FIRST EPSS API](https://www.first.org/epss/) or embedded in vulnerability scanner output.
- Score 0–1: Higher values = higher likelihood of active exploitation.
- **Decision**: EPSS + CVSS together provide both exploitability (EPSS) and impact (CVSS). A low-CVSS but high-EPSS vuln (e.g., RCE in test dependency) may warrant faster fix than high-CVSS but low-EPSS (e.g., theoretical overflow with no known exploit).

---

## 4. Image Promotion Workflow Definition

**Goal:** Build artifacts once, promote through environments to ensure audit trail and prevent configuration drift.

**Pattern:**

```
Code committed to main
   ↓
[CI Stage 1: Build & Test]
- Build container image: docker build . -t ${image}:${GIT_SHA}
- Run tests in container
- Run security scans (Trivy, SonarCloud)
- Push image to registry: ${registry}/${image}:${GIT_SHA}
- Tag as "latest": ${registry}/${image}:latest (optional, for easy reference)
   ↓
[CI Stage 2: Deploy to Dev]
- Deploy manifest referencing ${registry}/${image}:${GIT_SHA} (immutable SHA, not floating tag)
- Run integration tests in dev
- If pass, proceed to staging
   ↓
[CI Stage 3: Deploy to Staging]
- Reference same image SHA (${registry}/${image}:${GIT_SHA})
- Run smoke tests, performance tests
- If pass, await manual approval for prod
   ↓
[Manual Gate: Approval]
- Security team or release manager approves deployment to prod
   ↓
[CI Stage 4: Deploy to Production]
- Reference same image SHA (no rebuild)
- Canary deploy or blue-green switch
- Monitor health; rollback if needed
```

**Key Principles:**

1. **Single Build**: Image built once in CI; exact same artifact deployed to all environments.
2. **SHA References**: All deployments use `image@sha256:abc123...` (immutable), not `image:latest` (floating).
3. **No Rebuild**: Same `${GIT_SHA}` persists through all stages.
4. **Audit Trail**: Each promotion leaves a record in deployment logs / ArgoCD / GitOps tool.

**Anti-Pattern:**
```
❌ Build in dev → Build in staging → Build in prod
(Different artifacts, no reproducibility, harder to debug)
```

**Benefits:**
- **Reproducibility**: Same code → same image across all envs
- **Audit Trail**: Easy to trace which build version is where
- **Faster Deployments**: No time spent rebuilding in each stage
- **Reduced CVE Risk**: Scans happen once; deploy same scanned artifact everywhere

---

## 5. Example: End-to-End Assessment Report Flow

**Scenario:** Assess `bcgov/example-api` (NestJS backend + React frontend, OpenShift-deployed).

**Inspection Steps (mapped to Dimensions):**

| Dimension | Inspection | Finding |
| :--- | :--- | :--- |
| **1. Repo Settings** | `gh api graphql` → repo settings | Squash merge enabled ✅ |
| **2. Branch Rulesets** | `gh api graphql` → rulesets query | Main branch has PULL_REQUEST + STATUS_CHECKS ✅ |
| **3. Code Hygiene** | Read `tsconfig.json`, grep `@ts-ignore` | Strict mode on, zero escapes ✅ |
| **4. Secrets** | Read docs / SECURITY.md | Per-env tokens documented ✅ |
| **5. Dependency Updates** | Read `renovate.json`, trace preset | Renovate + BC Gov preset ✅ |
| **6. Vuln SLAs** | Read `.github/ISSUE_TEMPLATE/security.md` | SLA workflow documented ⚠️ EPSS not mentioned |
| **7. CI/CD** | Read workflows, manifests | Image promotion in place ✅ |
| **8. Quality Gates** | Read workflow steps | Coverage gate 85% ✅ |
| **9. OpenShift Security** | Read `*.deploy.yml` | All security contexts ✅ |

**Score Calculation:**
- Met: 8 dimensions
- Partial: 1 dimension (Vuln SLAs — missing EPSS integration)
- Score: (8 + 0.5) / 9 × 100 = **94%** → Level 5 (Optimizing)

**Report Output:** Generate `MATURITY_REPORT.md` in the audited repo with detailed checklist, findings per dimension, and remediation items.

---

## 6. Unverified vs. Not Met

**Distinction (Critical for Reproducibility):**

| State | Meaning | When to Use |
| :--- | :--- | :--- |
| **Met** (`[x]`) | All checks pass; comprehensive evidence | Standard pass |
| **Partial** (`[~]`) | At least one check passes, and at least one fails | 1–2 gaps identified (e.g., known vulns with scheduled fix) |
| **Not Met** (`[ ]`) | All checks fail; dimension is fundamentally absent | No branch protection configured; no dependency updates config |
| **Unverified** (`[?]`) | Data source unavailable; cannot assess | GitHub API inaccessible; cannot query rulesets |
| **N/A** (`[-]`) | Dimension does not apply to this repository type | Document-only or basic scripting repos with no software build/deploy |

**Rationale:** "Not Met" implies a **security gap**. "Unverified" means **inconclusive**, not a failure. Reporting "Not Met" when data source is unavailable invites fabricated findings and false negatives.

**Example:**
```markdown
### 2. Branch Protection Rulesets
- [?] **Unverified** ⚠️ (GitHub API access required)
      Unable to query rulesets without gh CLI authentication.
      Recommend: `gh auth login` and re-run, or manually inspect GitHub → Settings → Rules.
```

---

## Report Template

Use the following template when generating `MATURITY_REPORT.md` in the audited repository root.

### Executive Summary

```markdown
# Repository Compliance & Maturity Assessment

## Executive Summary

- **Repository:** `{REPO_NAME}`
- **Assessment Date:** `{YYYY-MM-DD}`
- **Overall Compliance Score:** `{SCORE}%`
- **Maturity Level:** `Level {1-5} - {Maturity Name}`
- **Report Prepared By:** {Agent Name} | **Next Review:** {Date, typically 30 days}

> **Maturity Scale:** Level 1 (Initial: <25%) | Level 2 (Developing: 25-49%) | Level 3 (Defined: 50-74%) | Level 4 (Managed: 75-89%) | Level 5 (Optimizing: >=90%)

> **Dimension Status:** Met | Partial | Not Met | **Unverified** (API/data unavailable; not a failure)
```

### Dimension Breakdown Table

```markdown
## Dimension Breakdown

| Dimension | Status | Findings & Notes |
| :--- | :---: | :--- |
| **1. GitHub Repo Settings** | `{Status}` | Squash merging, auto-delete, package visibility. |
| **2. Branch Protection Rules** | `{Status}` | Main branch rulesets, PR/approval/linear history/status checks. |
| **3. Language Code Hygiene** | `{Status}` | TS config strictness, linting, no diagnostic escapes, test coverage. |
| **4. OpenShift & Secrets** | `{Status}` | Token/password separation per environment, password strength. |
| **5. Dependency Update Automation** | `{Status}` | Renovate/Dependabot, BC Gov preset, release age, automerge. |
| **6. Vulnerability SLAs & Triage** | `{Status}` | Documented triage workflow, CISA KEV, EPSS, SLA enforcement. |
| **7. CI/CD & Deployments** | `{Status}` | PR preview envs, image promotion, SHA-based refs, health probes. |
| **8. CI-Enforced Quality Gates** | `{Status}` | TS/lint/test/coverage/scan failures block merge. |
| **9. OpenShift Security Contexts** | `{Status}` | Pod security contexts, capabilities, seccomp, probes. |
```

### Detailed Checklist

For each dimension, use checkbox format:
- `[x]` — Met
- `[~]` — Partial (at least one pass, at least one fail)
- `[ ]` — Not Met (all fail or fundamentally absent)
- `[?]` — Unverified (data source unavailable)
- `[-]` — Not Applicable (N/A)

Include per-dimension subsections with individual checks. For Dimension 5, include a **Renovate Configuration Inheritance Analysis** subsection documenting: local config, inherited preset settings, local overrides, effective configuration, and any conflicts.

### Scoring Formula

```markdown
## Scoring Formula

**Compliance Score (%)** = (Sum of Weighted Dimension Scores / Total Scored Dimensions) × 100

- **Met** (`[x]`): 1.0 points
- **Partial** (`[~]`): 0.5 points
- **Not Met** (`[ ]`): 0.0 points
- **Unverified** (`[?]`): Excluded from both numerator and denominator
- **N/A** (`[-]`): Excluded from both numerator and denominator
```

### Key Actions Required

```markdown
## Key Actions Required

**Tier 1 (Blocking — Complete Before Merge/Release):**
1. ...

**Tier 2 (Recommended — Complete Within 1 Sprint):**
1. ...

**Tier 3 (Optional — Backlog/Future Improvements):**
1. ...
```

