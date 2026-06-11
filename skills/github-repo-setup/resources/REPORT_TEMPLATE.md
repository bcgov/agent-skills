# Repository Compliance & Maturity Assessment

This report evaluates compliance against BC Gov DevOps & Dependency Security Standards. Detailed scoring rubric, dimension definitions, and remediation guidance are in [references/REFERENCE.md](../references/REFERENCE.md).

## Executive Summary

- **Repository:** `{REPO_NAME}`
- **Assessment Date:** `{YYYY-MM-DD}`
- **Overall Compliance Score:** `{SCORE}%` (see [Scoring Formula](#scoring-formula) below)
- **Maturity Level:** `Level {1-5} - {Maturity Name}`
- **Report Prepared By:** {Agent Name} | **Next Review:** {Date, typically 30 days}

> [!NOTE]
> **Maturity Scale:** Level 1 (Initial: <25%) | Level 2 (Developing: 25-49%) | Level 3 (Defined: 50-74%) | Level 4 (Managed: 75-89%) | Level 5 (Optimizing: >=90%)

> [!IMPORTANT]
> **Dimension Status:** Met | Partial | Not Met | **Unverified** (API/data unavailable; not a failure)

---

## Dimension Breakdown

| Dimension | Status | Findings & Notes |
| :--- | :---: | :--- |
| **1. GitHub Repo Settings** | `{Met/Partial/Not Met/Unverified}` | Squash merging, auto-delete, package visibility. *Requires GitHub API access; mark Unverified if unavailable.* |
| **2. Branch Protection Rules** | `{Met/Partial/Not Met/Unverified}` | Main branch rulesets, PR/approval/linear history/status checks enforcement. *Requires GitHub API (`gh api graphql`); mark Unverified if unavailable.* |
| **3. Language Code Hygiene** | `{Met/Partial/Not Met}` | TS config strictness, linting, no diagnostic escapes, test coverage (80%+). |
| **4. OpenShift & Secrets** | `{Met/Partial/Not Met}` | Token/password separation per environment, password strength (32+ chars). |
| **5. Dependency Update Automation** | `{Met/Partial/Not Met}` | Renovate/Dependabot, BC Gov preset, 7-day minimum release age, automerge, preset inheritance traced. |
| **6. Vulnerability SLAs & Triage** | `{Met/Partial/Not Met}` | Documented triage workflow, CISA KEV monitoring, EPSS scoring, SLA enforcement. |
| **7. CI/CD & Deployments** | `{Met/Partial/Not Met}` | PR preview envs, image promotion (no rebuilds), SHA-based refs, health probes. |
| **8. CI-Enforced Quality Gates** | `{Met/Partial/Not Met}` | TS/lint/test/coverage/scan failures block merge. |
| **9. OpenShift Security Contexts** | `{Met/Partial/Not Met}` | Pod security contexts (runAsNonRoot, readOnlyFS), capabilities, seccomp, probes. *See [openshift-deployment SKILL](../../openshift-deployment/SKILL.md) for remediation guidance.* |

---

## Detailed Check Checklist

### 1. GitHub Repository Configuration
- [ ] **Squash Merging Only:**
- [ ] **Branch Auto-Cleanup:**
- [ ] **Suggest Updates:**
- [ ] **Public Packages:**

### 2. Branch Protection Rulesets
- [ ] **Target Branch Protection:**
- [ ] **Bypass List Restricted:**
- [ ] **Deletion & Linear History:**
- [ ] **PR & Conversation Resolution Requirements:**
- [ ] **Status Checks Enforced:**
- [ ] **Security Scans Enforced:**
- [ ] **Force Pushes Blocked:**

### 3. Language & Code Hygiene
- [ ] **TypeScript / Strict Compilation Settings:** (If applicable)
- [ ] **Linting Configured and Enforced:** (JS/TS, Python, Java)
- [ ] **No Diagnostic/Type Escapes (`@ts-ignore`, `any`, `eslint-disable`):**
- [ ] **Test Coverage baseline (80%):**
- [ ] **Zero-Dependency Policy for Low-Volume Logic:**
- [ ] **Centralized Dependency Scanning Exception-free:**

### 4. OpenShift & Environment Secrets
- [ ] **Service Tokens Separation:**
- [ ] **Unique Passwords across environments:**
- [ ] **Password Strength:**

### 5. Dependency Update Automation
- [ ] **Renovate / Dependabot Configured:**
- [ ] **Pinned Config / Upstream BC Gov Configuration extended:**
- [ ] **Minimum Release Age (7 days):**
- [ ] **Automerge Policies:**
- [ ] **Dependency Dashboard active:**

#### Renovate Configuration Inheritance Analysis
**If Renovate is configured**, provide detailed preset tracing:

- **Local Config** (`renovate.json`):
  ```json
  {
    "extends": [
      "github>bcgov/renovate-config#VERSION"
    ]
  }
  ```

- **Inherited Preset** (from `github>bcgov/renovate-config#VERSION`):
  - `automerge`: {true/false}
  - `platformAutomerge`: {true/false}
  - `schedule`: {schedule expression}
  - `minimumReleaseAge`: {days}
  - `packageRules`: {list of grouping/filtering rules}
  - Other key settings: {list}

- **Local Overrides**: {any settings that override inherited config, or "None"}

- **Effective Configuration**:
  - Automerge status: {ENABLED / DISABLED}
  - Automerge scope: {e.g., minor/patch only, or all updates}
  - Update frequency: {schedule expression or inherited}
  - Safety margin: {minimumReleaseAge or "not configured"}

- **Conflicts or Concerns**: {any settings that may weaken security/automation, or "None identified"}

### 6. Security Vulnerability SLAs & Triage
- [ ] **No-Exemption SLA Policy:**
- [ ] **Exploit Status Triage Flow:**

### 7. CI/CD & Deployments
- [ ] **PR-Based Preview/Sandbox environments:**
- [ ] **Image Promotion workflow enabled (no environment rebuilding):**
- [ ] **Deep Health Checks configured:**

### 8. CI-Enforced Quality Gates & Dependency Budgets
- [ ] **CI-Enforced Quality Gates:**
- [ ] **Dependency Budgeting:**

### 9. OpenShift Container Security Contexts
- [ ] **Security Context Enforcements:**

---

## Scoring Formula

**Compliance Score (%)** = (Dimensions Met / Total Dimensions Scored) × 100

**Scoring Rules:**
- **Met**: All checks pass; count as 1.0
- **Partial**: Most checks pass; 1–2 minor gaps; count as 0.5
- **Not Met**: Majority of checks fail; count as 0.0
- **Unverified**: Data source unavailable (e.g., GitHub API down); **exclude from denominator** (do not penalize)
- **N/A**: Dimension not applicable to repo type (e.g., N/A for TypeScript on Python repo); **exclude from denominator**

**Example:**
```
Met: Dims 1, 3, 4, 5, 7, 8, 9 (7.0 points)
Partial: Dim 2 (0.5 points), Dim 6 (0.5 points)
Unverified: None
N/A: None

Score = (7.0 + 0.5 + 0.5) / 9 × 100 = 88.9% → Level 4 (Managed)
```

See [references/REFERENCE.md](../references/REFERENCE.md#1-scoring-rubric) for detailed rubric, weighting guidance, and N/A handling.

---

## Key Actions Required

List prioritized steps the development team needs to take to achieve complete compliance. Categorize by urgency:

**Tier 1 (Blocking — Complete Before Merge/Release):**
1. ...

**Tier 2 (Recommended — Complete Within 1 Sprint):**
1. ...

**Tier 3 (Optional — Backlog/Future Improvements):**
1. ...
