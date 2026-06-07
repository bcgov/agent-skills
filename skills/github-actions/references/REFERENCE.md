# github-actions — Deep Reference

Supplementary detail for [SKILL.md](../SKILL.md). Read the manifest first for the operational overview.

This reference is a worked example of BC Gov's GitHub Actions hardening: annotated workflows you can copy, a `permissions:` lookup table, a pinning decision matrix, the branch-protection settings the workflows assume, and a threat model mapping each rule back to the attack it defends against.

All examples use `bcgov/agent-skills` as the worked repo; substitute your own paths and package names.

---

## 1. Annotated PR Workflow — fork-gate + results aggregator

A `pull_request` workflow that lints, tests, validates artefacts, and exposes a single required status check.

```yaml
name: PR

# Runs on every pull request.
on:
  pull_request:

# Workflow-scope default: deny everything. Each job opts in only to the scopes it needs.
permissions: {}

jobs:
  # 0. Hard gate: fail loudly on PRs opened from a fork. Produces a real failed
  #    status check (not a neutral "skipped") so branch protection sees it.
  fork-gate:
    runs-on: ubuntu-24.04
    # No checkout, no API calls — inherits the workflow's deny-all permissions.
    steps:
      - name: Reject PRs from forks
        env:
          HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name }}
          BASE_REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          if [ "$HEAD_REPO" != "$BASE_REPO" ]; then
            echo "PR opened from fork ($HEAD_REPO); re-land it from a branch in $BASE_REPO."
            exit 1
          fi

  # 1. Lint + tests. Gated on fork-gate. Needs to read the repo.
  lint-tests:
    needs: fork-gate
    runs-on: ubuntu-24.04
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6   # first-party → major tag is fine
        with:
          fetch-depth: 0            # full history to diff against base branch

      - name: Install uv
        uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          version: "0.11.19"
          enable-cache: true

      - name: Check formatting
        run: uv run ruff format --check .

      - name: Lint
        run: uv run ruff check .

      - name: Tests
        run: uv run pytest -q

  # 2. Domain validation. Gated on lint-tests.
  skills:
    needs: lint-tests
    runs-on: ubuntu-24.04
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          version: "0.11.19"
          enable-cache: true

      - name: Validate changed skills
        run: uv run python scripts/validate_skill.py --base "origin/${{ github.base_ref }}"

  # 3. Aggregator. The SINGLE required status check on `main`.
  results:
    if: always()
    needs: [fork-gate, lint-tests, skills]
    runs-on: ubuntu-24.04
    # No permissions needed — inherits the workflow's deny-all default.
    steps:
      - name: Fail if any required job failed or was cancelled
        if: contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')
        run: |
          set -euo pipefail
          echo "At least one required job failed or was cancelled."
          echo '${{ toJSON(needs) }}'
          exit 1

      - name: All required jobs passed
        run: echo "All required jobs passed (or were intentionally skipped)."
```

**Why this shape**:

- Workflow-scope `permissions: {}` is the BC Gov default — deny everything, then jobs that need access (here, `lint-tests` and `skills` need `contents: read` to check out) opt in explicitly.
- The `results` job is the only check named in branch protection. Renaming `lint-tests` to `lint` or splitting `skills` into two jobs never touches the ruleset.
- `if: always()` ensures `results` runs even when an upstream job fails — without it, branch protection would see the required check as `skipped` and the merge would be blocked indefinitely.
- `skipped` is treated as a pass on purpose so conditional jobs (e.g. one with `if: contains(github.event.head_commit.message, 'docs')`) don't false-fail the gate.
- Inputs from `github.event.pull_request.head.repo.full_name` go through `env:` and shell-quoted `"$HEAD_REPO"`, so a forked repo with a payload in its name can't escape the comparison.
- `set -euo pipefail` at the top of every multi-line `run:` block makes failures loud: an unset variable is a hard error, not an empty string; a failing left-hand side of a pipe propagates instead of being masked by a zero exit on the right.

---

## 2. Annotated Publish Workflow — path filter + version skip + least-privilege

Publishes to GitHub Packages npm on a `main` push, but only when files under `skills/**` actually change, and skips any version already on the registry.

```yaml
name: Publish

on:
  push:
    branches: [main]
    paths:
      - "skills/**"
      - ".github/workflows/publish.yml"
      - ".github/scripts/publish-changed-skills.sh"

# Workflow scope: deny-all. The publish job opts in to the narrow scopes it needs.
permissions: {}

concurrency:
  group: publish
  cancel-in-progress: false   # never cancel a mid-flight publish

jobs:
  publish:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      packages: write          # only escalation: needed for `npm publish` to GHCR npm
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0       # for the version-skip diff

      - uses: actions/setup-node@v6
        with:
          node-version: "24"
          registry-url: "https://npm.pkg.github.com"
          scope: "@bcgov"

      - name: Publish changed skills (version-skip if already on registry)
        env:
          NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: bash .github/scripts/publish-changed-skills.sh
```

**Why this shape**:

- `paths:` filter means the workflow doesn't burn minutes when the change is docs-only or workflow-only-unrelated.
- `permissions: {}` at workflow scope means **no token capabilities by default** — the publish job explicitly opts in to `contents: read` (for checkout) and `packages: write` (for `npm publish`). Any helper job added later starts at deny-all and has to opt in explicitly.
- `NODE_AUTH_TOKEN` uses the built-in `GITHUB_TOKEN`, not a PAT. The token lives only for the workflow's duration and respects the job's `permissions:` ceiling.
- `concurrency: { group: publish, cancel-in-progress: false }` prevents two pushes from racing each other to publish the same version (`npm publish` is not idempotent for in-flight tarballs).
- The publish script's job is to be **idempotent** — it inspects each skill's `package.json` version, queries the registry, and skips the `npm publish` if that exact version already exists. A merge only ships what was actually bumped.
- The script itself starts with `set -euo pipefail` so a single failed publish stops the loop instead of marching on and reporting success.

---

## 3. Annotated Pages Workflow — OIDC + build/deploy split

Deploys a static site from `docs/` on every push to `main`. Uses GitHub's official Pages OIDC flow (no PAT, no Pages deploy key).

```yaml
name: Deploy GitHub Pages

on:
  push:
    branches: [main]
    paths:
      - "docs/**"
      - ".github/workflows/pages.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write              # for OIDC to Pages

concurrency:
  group: pages
  cancel-in-progress: false    # don't cancel a publish in flight

jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-node@v6
        with:
          node-version: "24"

      - name: Build documentation
        run: |
          set -euo pipefail
          cd docs
          chmod +x build.sh
          ./build.sh

      - uses: actions/configure-pages@v6
      - uses: actions/upload-pages-artifact@v5
        with:
          path: docs

  deploy:
    needs: build
    runs-on: ubuntu-24.04
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v5
```

**Why this shape**:

- Build and deploy split so the deploy job has the narrow surface area Pages OIDC expects (`id-token: write` only needs to be claimed by a job that actually exchanges it).
- `environment: github-pages` is what binds the deploy to the repo's *Settings → Pages* config.
- The whole pipeline is keyless: no PAT, no deploy key, no `GH_TOKEN: …`.

---

## 4. Dependabot — config + auto-merge

Two files. Together they bump every action / runtime and auto-merge low-risk PRs without a maintainer.

`.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    groups:
      actions-minor-patch:
        update-types:
          - minor
          - patch
    commit-message:
      prefix: "deps(actions)"

  - package-ecosystem: npm
    directory: /
    schedule:
      interval: weekly
    groups:
      npm-minor-patch:
        update-types:
          - minor
          - patch
    commit-message:
      prefix: "deps(npm)"

  - package-ecosystem: pip
    directory: /
    schedule:
      interval: weekly
    commit-message:
      prefix: "deps(pip)"
```

`.github/workflows/dependabot-auto-merge.yml`:

```yaml
name: Dependabot Auto Merge

on:
  pull_request_target:        # required: pull_request from Dependabot has read-only token
    types: [opened, reopened, synchronize]

permissions:
  contents: write             # to merge
  pull-requests: write        # to approve

concurrency:
  group: dependabot-auto-merge-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  auto-approve-and-merge:
    if: github.event.pull_request.user.login == 'dependabot[bot]'   # STRICT actor gate
    runs-on: ubuntu-24.04
    steps:
      - name: Approve Dependabot PR
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_URL: ${{ github.event.pull_request.html_url }}
        run: gh pr review --approve "$PR_URL"

      - name: Enable auto-merge
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_URL: ${{ github.event.pull_request.html_url }}
        run: gh pr merge --auto "$PR_URL"
```

**Why this shape — and why it's safe**:

- `pull_request_target` is the **only** trigger that lets a Dependabot PR mutate the repo (PR token is read-only on `pull_request`). It runs in the base repo's context with the base repo's secrets, which is why it's normally dangerous.
- The `if:` actor gate makes it safe: the job body only runs when the PR author is literally `dependabot[bot]`. Any other PR opener (including a fork attacker) sees the job skip.
- The workflow never `actions/checkout`s the PR head SHA. It calls `gh` against PR metadata only — no PR code is ever executed in the privileged context.
- `concurrency` cancels in-flight runs when Dependabot pushes a force-update to the same PR (which is common as the auto-merge waits for status checks).
- Repo-side: enable *Settings → General → Pull Requests → Allow auto-merge*. Without it, `gh pr merge --auto` errors.

---

## 5. `permissions:` scope lookup table

Start with `permissions: {}` (deny-all) at workflow scope, or `contents: read` if every job legitimately needs to read the repo. Add scopes only on the specific job that needs them.

| Scope                 | What it grants                                                              | Add when …                                                                  |
| --------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `permissions: {}`     | Nothing — deny-all baseline                                                 | Workflow scope, every workflow, as the BC Gov default starting point.       |
| `contents: read`      | Read repo files, history, releases                                          | Any job that runs `actions/checkout` or reads release metadata.             |
| `contents: write`     | Push commits, create tags, create releases, write release assets            | Auto-merge, release-please, `git push` from CI.                             |
| `pull-requests: write`| Open/edit PRs, post review approvals, set labels                            | Bot-comment workflows, auto-approve, auto-merge.                            |
| `issues: write`       | Open/edit issues, comment, label                                            | Triage bots, "stale" actions.                                               |
| `packages: write`     | `npm publish`, push container images to GHCR                                | The publish job only.                                                       |
| `packages: read`      | `npm install` private GHCR packages                                         | Any job that consumes `@bcgov/*` packages.                                  |
| `pages: write`        | Deploy to GitHub Pages via the official actions                             | Pages deploy job only.                                                      |
| `id-token: write`     | Mint an OIDC token for federation (Pages, AWS, Azure, sigstore)             | OIDC-based deploys.                                                         |
| `actions: read`       | Read other workflows' run metadata                                          | "Required workflows" reporting, run-skipping logic.                         |
| `actions: write`      | Cancel runs, dispatch workflows                                             | Avoid; usually not needed.                                                  |
| `checks: write`       | Create check runs (richer than status checks)                               | Custom CI reporters; most jobs don't need this.                             |
| `security-events: write` | Upload SARIF (CodeQL, Snyk, Trivy)                                       | Scanner jobs only.                                                          |

Anything you don't list is implicitly **denied** when you supply *any* `permissions:` block. That's the point: explicit allow-list, no inheritance from the repo default.

---

## 6. Action pinning decision matrix

| Class                                      | Pin format                                | Example                                                                                |
| ------------------------------------------ | ----------------------------------------- | -------------------------------------------------------------------------------------- |
| First-party (`actions/*`)                  | Major tag                                 | `uses: actions/checkout@v6`                                                            |
| First-party (`github/*`)                   | Major tag                                 | `uses: github/codeql-action/init@v3`                                                   |
| Third-party with stable release cadence    | Commit SHA + version comment              | `uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0`           |
| Third-party with only tags (no SHA pin)    | Fork to BC Gov org, pin fork by SHA       | `uses: bcgov/forked-action@<sha> # forked from upstream@1.2.3`                         |
| Container actions (`docker://`)            | Image digest                              | `uses: docker://ghcr.io/owner/img@sha256:abc...`                                       |
| Local actions (`./`)                       | Path only                                 | `uses: ./.github/actions/internal-helper`                                              |
| Reusable workflows (`org/repo/.../wf@ref`) | Same rule as the action: major tag or SHA | `uses: bcgov/shared-workflows/.github/workflows/lint.yml@v2`                           |

Dependabot understands both styles. If you SHA-pin without the `# v8.2.0` comment, Dependabot still works but the diff is unreviewable — keep the comment.

---

## 7. Branch protection / ruleset checklist

What the BC Gov default ruleset for `main` should contain (settable via *Settings → Rules → Rulesets* or the legacy *Settings → Branches → Branch protection rules*):

- [x] **Require a pull request before merging.** Approvals: 0 by default; raise per repo policy. Dismiss stale approvals on push.
- [x] **Require status checks to pass.** Strict (PR must be up to date with base). Required check: the single `results` job from your PR workflow. Nothing else.
- [x] **Require signed commits.** Enforced for everyone — admins included if the repo policy says so.
- [x] **Block force pushes.**
- [x] **Block branch deletion.**
- [x] **Restrict who can push directly to `main`.** No one, ideally — even admins go through PR.
- [x] **Require linear history** if your release flow expects it (squash-or-rebase merges). Skip if you rely on merge commits.
- [ ] **Lock branch.** Off — `main` accepts merges.
- [x] **CodeQL or similar code scanning** as an additional required check on repos that have it.

Mirror this same shape across BC Gov repos so contributors get a consistent experience.

---

## 8. Threat model — which rule defends which attack

| Attack                                                                                                    | Defence                                                                  |
| --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **Action tag hijack** — attacker compromises an upstream action's release tag and ships an exfil payload  | SHA-pin third-party actions; let Dependabot bump SHAs through review.    |
| **Fork PR token exfil** — fork PR's workflow run reads `secrets.*` from the base repo                     | `fork-gate` job; `secrets` are not passed to fork-PR runs by default.    |
| **Script injection via PR title / branch name / issue body**                                              | Pass attacker input through `env:`, quote `"$VAR"` in shell.             |
| **`pull_request_target` abuse** — fork PR triggers a privileged workflow that runs the PR's code          | Never checkout + execute the PR head SHA in `pull_request_target`. Actor-gate the job.       |
| **PAT sprawl / orphan PATs** — a long-lived PAT outlives its owner / its purpose                          | Use the built-in `GITHUB_TOKEN` or OIDC; never paste a PAT into a secret.|
| **Required check rename** — branch protection no longer recognises the check and silently auto-approves   | Single `results` aggregator as the only required check; rename freely.   |
| **Workflow added to `main` that grants itself `write-all`**                                               | Repo default *Workflow permissions* set to read; workflows must opt in.  |
| **A `*-latest` runner alias (`ubuntu-latest` / `windows-latest` / `macos-latest`) rolls a new major version overnight and breaks tooling** — Xcode majors and SDK churn on macOS, Visual Studio component updates on Windows, glibc / Python defaults on Ubuntu | Pin to a specific version label (`ubuntu-24.04`, `windows-2025` / `windows-2022`, `macos-26` / `macos-15`); upgrades become a deliberate, reviewable PR. |
| **Force-push to `main` rewrites history during an incident**                                              | Branch ruleset blocks force-push and deletion.                           |
| **Unsigned commit lands on `main` and bypasses provenance**                                               | Branch ruleset *Require signed commits* (cannot be temporarily disabled in practice). |
| **In-flight publish cancelled by a newer push**                                                           | `concurrency: { group: publish, cancel-in-progress: false }`.            |
| **Multi-line `run:` block silently swallows a failure on the left of a pipe**                             | `set -euo pipefail` as the first line of every non-trivial `run:` block. |
| **Missing secret silently becomes an empty string and bricks a `gh` call as a no-op success**             | `set -u` (part of `-euo pipefail`) makes the unset variable a hard fail. |
| **Long-lived cloud-credential exfil** — `AZURE_CLIENT_SECRET` or AWS access key in `secrets.*` is stolen via tag hijack, `pull_request_target` slip, or insider | OIDC federation: `id-token: write` on the deploy job, official provider action SHA-pinned per §6 (`azure/login@<sha> # v3.0.0`, `aws-actions/configure-aws-credentials@<sha> # v6`), and a cloud-side federated-credential subject that pins repo + environment / ref. No `*_SECRET` / `*_KEY` in `secrets.*`. |

---

## 9. Error → root cause cheat sheet

| Message                                                                       | Cause                                                                                            | Fix                                                                                                                                            |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `Resource not accessible by integration`                                      | The job's `permissions:` block doesn't include the scope the API call needs                       | Add the narrow scope on **the job**, not the workflow.                                                                                         |
| `Refusing to allow a Personal Access Token to create workflow`                | A PAT is trying to push a `.github/workflows/` change                                            | Use `GITHUB_TOKEN` (which can) or a fine-grained PAT with explicit "Workflows" permission. Better: stop pushing workflow files from CI.        |
| `npm ERR! 401 Unauthorized` on publish                                        | `NODE_AUTH_TOKEN` not set, or `permissions: { packages: write }` missing on the job              | Set `env: NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` on the publish step and grant `packages: write` on the job.                            |
| `npm ERR! 403 Forbidden — You cannot publish over the previously published versions` | A version that's already on the registry is being re-published                                   | Bump the version in the changed skill's `package.json` (the publish script's version-skip should normally prevent this; investigate the diff). |
| Required check name appears as `Expected — Waiting for status` forever        | The required check's name was renamed in the workflow file but not in branch protection         | Switch to a `results` aggregator as the single required check, then renames are free.                                                          |
| `Auto-merge is not allowed for this repository`                               | Repo setting *Allow auto-merge* is off                                                            | *Settings → General → Pull Requests → Allow auto-merge*.                                                                                       |
| Dependabot PR opens but no auto-merge workflow runs                           | The workflow uses `pull_request` instead of `pull_request_target` — Dependabot's PR token is read-only | Switch the trigger to `pull_request_target` and keep the strict actor gate.                                                                |
| `Error: The process '/usr/bin/git' failed with exit code 128`                 | Checkout couldn't fetch enough history for a diff-based step                                     | Add `with: { fetch-depth: 0 }` to `actions/checkout`.                                                                                          |
| Workflow runs on every push even when nothing it cares about changed          | Missing `paths:` filter                                                                          | Add `paths:` (or `paths-ignore:`) to scope the trigger.                                                                                        |
| `pull_request_target` workflow exposed a secret to a fork PR                  | Job didn't gate on actor and used the elevated token                                              | Add `if: github.event.pull_request.user.login == '<expected-actor>'` and never checkout the PR head SHA.                                       |
| `AADSTS70021: No matching federated identity record found` (Azure) / `Not authorized to perform sts:AssumeRoleWithWebIdentity` (AWS) | Cloud-side federated credential's subject claim doesn't match the workflow's actual `sub` (branch / env / PR mismatch) | Update the Federated Identity Credential (Entra) or IAM OIDC trust to match the runtime `sub` — typically `repo:OWNER/REPO:environment:NAME`, `repo:OWNER/REPO:ref:refs/heads/main`, or `repo:OWNER/REPO:pull_request`. Don't add a `client-secret` / access key to "unblock". |

---

## 10. Pre-merge local validation

Before opening the PR:

```bash
# YAML lint (the repo's .yamllint allows `on:` as a truthy key)
yamllint .github/workflows/

# Shellcheck any non-trivial run: blocks (extract them or use actionlint)
# https://github.com/rhysd/actionlint pulls them out for you.
actionlint

# Full repo gate (matches what `results` will run on the PR)
make lint test validate
```

If `actionlint` is unavailable, the GitHub Marketplace has a Docker variant that runs the same checks in 2–3s.

---

## 11. Conventional Commit scopes for workflow / action PRs

The BC Gov standard is Conventional Commits with the scope derived from the primary directory touched. For GHA work that maps cleanly to a small vocabulary — keep PR titles aligned with what Dependabot is already emitting so changelog tooling stays consistent.

| What changed                                                | Type + scope                                  | Example                                                                 |
| ----------------------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------- |
| Edit a workflow file (`.github/workflows/<x>.yml`)          | `ci(workflows)`                               | `ci(workflows): add concurrency group to publish`                       |
| Add a helper script under `.github/scripts/`                | `ci(scripts)`                                 | `ci(scripts): make publish-changed-skills.sh idempotent`                |
| Bump a pinned action SHA / tag                              | `deps(actions)`                               | `deps(actions): bump astral-sh/setup-uv to v8.3.0`                      |
| Bump a runtime in a workflow (`node-version`, Python, etc.) | `ci(workflows)` (or `deps(<ecosystem>)`)      | `ci(workflows): pin Node to 24`                                         |
| Bump `npm` / `pip` deps used by a workflow                  | `deps(npm)` / `deps(pip)`                     | `deps(npm): bump @octokit/core to 6.x`                                  |
| Tweak Dependabot config                                     | `ci(dependabot)`                              | `ci(dependabot): group minor + patch updates`                           |
| Edit branch protection / ruleset config in code             | `chore(rules)` or `ci(ruleset)`               | `ci(ruleset): require strict status checks on main`                     |

Dependabot in this repo already emits `deps(actions)`, `deps(npm)`, `deps(pip)` via `commit-message.prefix` — see [`.github/dependabot.yml`](../../../.github/dependabot.yml). Human PRs should follow the same shape.

---

## 12. Cloud login — OIDC federation (Azure / AWS)

The BC Gov default for any workflow that deploys to a public cloud is **OIDC federation** — no long-lived `AZURE_CLIENT_SECRET` or AWS access key in `secrets.*`. The deploy job claims `id-token: write`, the official provider action exchanges the short-lived GitHub OIDC token for a cloud credential, and the cloud-side trust pins the GitHub repo + ref so a fork or a non-`main` branch cannot exchange it.

### Azure (`azure/login`)

```yaml
jobs:
  deploy:
    runs-on: ubuntu-24.04
    environment: prod              # ties this run to the federated cred's environment subject
    permissions:
      contents: read
      id-token: write              # mint the OIDC token; granted on the deploy job ONLY
    steps:
      - uses: actions/checkout@v6

      - name: Azure CLI login (OIDC)
        uses: azure/login@532459ea530d8321f2fb9bb10d1e0bcf23869a43 # v3.0.0
        with:
          client-id:       ${{ secrets.AZURE_CLIENT_ID }}        # identifier, not a credential
          tenant-id:       ${{ secrets.AZURE_TENANT_ID }}        # identifier, not a credential
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}  # identifier, not a credential
          # NO client-secret. If you ever add one, you've defeated the point of OIDC.

      - run: az account show
```

The three `secrets.*` values above are stored in repo / org / environment secrets purely as **configuration** — they're just GUIDs and an Entra app registration ID. The actual trust is established by a [Federated Identity Credential](https://learn.microsoft.com/entra/workload-id/workload-identity-federation-create-trust) on the Entra app (or User-Assigned Managed Identity), whose `subject` claim pins exactly which workflow can mint a token for it.

`azure/login` is owned by Microsoft, not GitHub (`actions/*` / `github/*`), so it falls under §6's "third-party with stable release cadence" rule — SHA-pin with a `# v3.0.0` (or `# v3`) comment so Dependabot can still propose bumps as reviewable diffs.

### AWS (`aws-actions/configure-aws-credentials`)

Structured as a reusable workflow (`on: workflow_call`) so `inputs.environment_name` resolves — the same shape works under `workflow_dispatch` with an input of the same name.

```yaml
on:
  workflow_call:
    inputs:
      environment_name:
        type: string
        required: true

env:
  AWS_REGION: ca-central-1     # single source of region for every aws-* step in this job

jobs:
  deploy:
    runs-on: ubuntu-24.04
    environment: ${{ inputs.environment_name }}   # binds the run (and its OIDC sub) to the named env
    permissions:
      contents: read
      id-token: write                              # mint the OIDC token; granted on the deploy job ONLY
    steps:
      - uses: actions/checkout@v6

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@8df5847569e6427dd6c4fb1cf565c83acfa8afa7 # v6
        with:
          role-to-assume:    ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          role-session-name: ${{ inputs.environment_name }}-deployment
          aws-region:        ${{ env.AWS_REGION }}
          # NO aws-access-key-id / aws-secret-access-key. AssumeRoleWithWebIdentity does the rest.

      - run: aws sts get-caller-identity
```

**Why this shape**:

- `aws-actions/*` is AWS-owned, not first-party `actions/*` or `github/*`, so it falls under "third-party with stable release cadence" in §6 — SHA-pin with a `# v6` (or full `# v6.2.0`) comment so Dependabot can still propose bumps as reviewable diffs.
- `role-session-name: ${{ inputs.environment_name }}-deployment` shows up in CloudTrail as the assumed-role session identifier — a per-environment name (`prod-deployment`, `test-deployment`) makes "who ran what against which account?" answerable from CloudTrail alone, without cross-referencing GitHub run IDs.
- `secrets.AWS_DEPLOY_ROLE_ARN` keeps the role ARN out of the workflow file. ARNs aren't sensitive — `vars.AWS_DEPLOY_ROLE_ARN` works too — but parameterising lets the same reusable workflow be called from multiple repos / environments, each binding to a different IAM role.
- `env.AWS_REGION` at job scope means subsequent `aws …` CLI steps inherit the region automatically — no risk of one step targeting `ca-central-1` and the next defaulting to `us-east-1`.
- `environment: ${{ inputs.environment_name }}` binds the run to the named GitHub Environment, so the OIDC token's `sub` claim becomes `repo:OWNER/REPO:environment:<environment_name>` — exactly the strongest subject shape from the cookbook below, and it composes with the Environment's required-reviewers gate.

IAM side: create an [OIDC identity provider](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) pointing at `https://token.actions.githubusercontent.com` and one IAM role per environment (`AWS_DEPLOY_ROLE_ARN`), each whose trust policy pins `token.actions.githubusercontent.com:sub` to its own `repo:OWNER/REPO:environment:<env>` subject — so the `prod` role can only be assumed from runs bound to the `prod` Environment, and so on.

### Federated-credential subject-claim cookbook

The cloud-side trust pins the workflow by a **subject claim** that must match the GitHub OIDC token's `sub` field exactly. Pick the most restrictive shape that fits the deploy:

| Use case                                              | Subject claim                                                   |
| ----------------------------------------------------- | --------------------------------------------------------------- |
| Deploy from a specific GitHub **environment**         | `repo:OWNER/REPO:environment:prod`                              |
| Deploy from a specific **branch**                     | `repo:OWNER/REPO:ref:refs/heads/main`                           |
| Deploy from a specific **tag** (pattern)              | `repo:OWNER/REPO:ref:refs/tags/v*`                              |
| Run from a PR (rarely needed; usually never grant)    | `repo:OWNER/REPO:pull_request`                                  |

**Prefer the `environment:` shape** — it composes with GitHub's *Settings → Environments → Required reviewers / Wait timer / Deployment branches* gates, so the cloud-side trust automatically inherits any human-approval gate you configure. Without `environment:`, any push to the matching `ref:` can mint a token.

The strongest BC Gov default is a deploy job with both `environment: prod` and a federated credential whose subject is `repo:OWNER/REPO:environment:prod`, plus Required Reviewers on the `prod` environment so the OIDC token is only mintable after human approval. That makes the entire deploy path **keyless and human-gated**, with no long-lived cloud secret anywhere in the system.
