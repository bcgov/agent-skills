# Repository Compliance & Maturity Assessment

This report evaluates compliance against BC Gov DevOps & Dependency Security Standards (see [skill documentation](../SKILL.md) for detailed requirements).

## Executive Summary

- **Repository:** `{REPO_NAME}`
- **Assessment Date:** `{YYYY-MM-DD}`
- **Overall Compliance Score:** `{SCORE}%`
- **Maturity Level:** `Level {1-5} - {Maturity Name}`

> [!NOTE]
> **Maturity Scale:** Level 1 (Initial: <25%) | Level 2 (Developing: 25-49%) | Level 3 (Defined: 50-74%) | Level 4 (Managed: 75-89%) | Level 5 (Optimizing: >=90%)

---

## Dimension Breakdown

| Dimension | Compliance | Findings & Notes |
| :--- | :---: | :--- |
| **1. GitHub Repo Settings** | `{Met / Not Met / N/A}` | Squash merging, auto-delete head branches, package visibility. |
| **2. Branch Protection Rules** | `{Met / Not Met / N/A}` | Main branch rulesets, bypass restrictions, mandatory PR approvals, linear history. |
| **3. Language Code Hygiene** | `{Met / Not Met / N/A}` | TS config strictness, linting configs, no diagnostic bypass comments, test coverage, zero-dependency checks. |
| **4. OpenShift & Secrets** | `{Met / Not Met / N/A}` | Multi-environment tokens/secrets, password strength & separation. |
| **5. Dependency Update Automation** | `{Met / Not Met / N/A}` | Renovate or Dependabot config, pinned configuration, minimum release age (7 days), automerge. |
| **6. Vulnerability SLAs & Triage** | `{Met / Not Met / N/A}` | Security vulnerability triage flow, exploit status checks (CISA KEV / EPSS). |
| **7. CI/CD & Deployments** | `{Met / Not Met / N/A}` | PR-based preview/sandbox environments, image promotion workflow (no rebuilding same code). |
| **8. CI-Enforced Quality Gates** | `{Met / Not Met / N/A}` | Build failures on warnings/diagnostics, transitive dependency budgeting. |
| **9. OpenShift Security Contexts** | `{Met / Not Met / N/A}` | Pod security context settings (`runAsNonRoot`, `readOnlyRootFilesystem`). |

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

## Key Actions Required

List prioritized steps the development team needs to take to achieve complete compliance. Focus on contract violations first:

1. **[High Priority]** ...
2. **[Medium Priority]** ...
3. **[Low Priority]** ...
