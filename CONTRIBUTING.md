# Contributing to agent-skills

Thanks for helping build BC Gov's shared library of agent skill profiles. This
repository is community-maintained — new skills and improvements to existing
ones are all welcome.

## Before you start

Contributions are made through pull requests from a branch **in this
repository**, not from a fork. The PR workflow
([.github/workflows/pr.yml](.github/workflows/pr.yml)) has a `fork-gate` job
that fails any pull request opened from a fork; that failure cascades to the
`results` aggregator, which is the gate on merge. If you can't push a branch to
this repository, you don't have the access you need — sort that out before
opening a PR.

**Commits must be signed.** The `main` branch ruleset requires signed commits,
so the merge will be blocked otherwise. Set up SSH or GPG commit signing once
per machine — see [GitHub's docs](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification).

## How contributions work

1. **Branch** — create a feature branch in this repo for your change. (Forks
   are not supported by the PR workflow.)
2. **Add or update a skill** — for a new skill, first confirm no [upstream
   catalog](#before-adding-a-new-skill-check-upstream-catalogs-first) already
   covers it. Then follow [spec/SKILL_SPEC.md](spec/SKILL_SPEC.md) and copy an
   existing skill's `SKILL.md` as a starting point
   (e.g. [`skills/azure-networking/SKILL.md`](skills/azure-networking/SKILL.md)).
3. **Validate locally** — `uv run python scripts/validate_skill.py skills/<name>/SKILL.md`.
4. **Open a pull request** — describe what the skill does and why it's useful.
5. **Pass the checks** — the PR workflow validates the skills your branch
   changed (diffed against the base branch).
6. **Merge** — once the `results` check is green and your branch is up to date
   with `main`, the PR can be merged (squash or merge commit; rebase is
   disabled). Consumers pick up the change the next time they run
   `npx skills add bcgov/agent-skills`. Review is encouraged but not gated by
   the ruleset — see [Review expectations](#review-expectations).

## Before adding a new skill: check upstream catalogs first

This repository is for **BC Gov–specific** skills. Before adding a new skill,
confirm it isn't already published in an upstream catalog. Duplicating an
upstream skill fragments the ecosystem, doubles the maintenance burden, and
makes it ambiguous which one consumers should install.

Check these first:

1. **[The Agent Skills Directory](https://www.skills.sh/)** — a
   vendor-neutral directory of agent skills aggregated across publishers. Good
   first stop for a broad sweep before drilling into the publisher-specific
   catalogs below.
2. **[Microsoft Agent Skills catalog](https://microsoft.github.io/skills/#agents)**
   — a large catalog of skills covering Azure SDKs, Microsoft Foundry, M365,
   Entra, Azure Resource Manager, plus cross-cutting workflows (`azure-prepare`,
   `azure-deploy`, `azure-validate`, `azure-cost`, `microsoft-docs`, `kql`,
   `mcp-builder`, `cloud-solution-architect`, and others).
3. **[Anthropic's `anthropics/skills`](https://github.com/anthropics/skills)** —
   reference skills for document work (`pdf`, `docx`, `xlsx`, `pptx`) and other
   patterns, plus material on the SKILL.md format this repo follows (see also
   [agentskills.io](https://agentskills.io)).
4. **[awesome-copilot](https://github.com/github/awesome-copilot)** — the
   community-curated index of skills, prompts, custom agents, and hooks; it
   also distributes vendor plugin catalogs (M365 Agents Toolkit, Power BI,
   Oracle-to-PostgreSQL, Spark, WorkIQ, and others) so one check covers them.

If a skill that covers your use case already exists upstream:

- **Don't re-publish it here.** Point consumers at the upstream skill instead.
- **If it's close but not quite right**, prefer opening an issue or PR against
  the upstream skill so the fix benefits the largest audience. Forking it here
  should be a last resort.
- **Only add a new skill in this repo if** it is genuinely BC Gov–specific —
  e.g., it encodes BC Gov policies, conventions, internal services, regulatory
  requirements, or organization-specific workflows that have no place in a
  generic upstream catalog.

Include the result of this check in your PR description — either "no upstream
skill covers this" with a one-line justification, or a link to the upstream
skill plus the BC Gov–specific gap that justifies a separate skill. Reviewers
will ask for it otherwise.

## Skill structure

Each skill lives in its own directory. The whole directory is what consumers
install with `npx skills add`, so put everything the skill needs alongside its
manifest:

```
skills/<skill-name>/
├── SKILL.md        # required: the manifest
├── scripts/        # optional: executable helpers
├── references/     # optional: heavy detail
└── assets/         # optional: examples & resources
```

`SKILL.md` needs mandatory `name` + `description` frontmatter, then a body with
an H1 title and the seven required sections (Use When, Don't Use When, Workflow,
Rules, Examples, Edge Cases, References). `name` must be kebab-case (≤64 chars)
and match the skill's directory name; `description` must be ≤1024 chars with no
angle brackets. Keep the manifest under 500 lines and any `scripts/`,
`references/`, or `assets/` directory flat (one level deep). See the spec for
the full definition.

## Tooling

This project uses [uv](https://docs.astral.sh/uv/) — there is no
`requirements.txt`. Dependencies are declared in `pyproject.toml` and installed
on demand by `uv run`. Common commands:

```bash
make format     # auto-format Python (2-space indent, double quotes)
make lint       # lint Python with ruff + workflow YAML with yamllint
make test       # run the validator unit tests
make validate   # validate every skill
```

Python is formatted and linted with [ruff](https://docs.astral.sh/ruff/),
configured in `pyproject.toml` (2-space indentation, double quotes, and
docstrings required on every function). Workflow YAML under
`.github/workflows/` is linted with [yamllint](https://yamllint.readthedocs.io/),
configured in `.yamllint` at the repo root. Run `make format` before pushing.

## PR checks

The PR workflow ([.github/workflows/pr.yml](.github/workflows/pr.yml)) runs four
jobs in three phases:

0. **fork-gate** — runs first and fails if the PR's head repo is not this repo.
   The failure cascades to `results`, so fork PRs cannot merge.
1. **lint-tests** — runs after `fork-gate`, because broken tooling makes
   validating skill output meaningless. It checks the code that produces skills:
   - `uv run ruff format --check .` — Python is correctly formatted,
   - `uv run ruff check .` — lint, import order, and docstring coverage pass,
   - `uv run pytest -q` — the validator's unit tests pass.
2. **skills** — runs only after `lint-tests` passes. It runs
   `scripts/validate_skill.py` against the skills your PR changed (diffed
   against the base branch) and confirms:
   - the frontmatter block exists, is closed, and parses as a mapping,
   - `name` and `description` are present and non-empty,
   - `name` is kebab-case (≤64 chars) and matches the skill's directory name,
   - `description` is ≤1024 chars with no angle brackets,
   - no unexpected frontmatter keys are present (only `name`, `description`,
     `owner`, `tags`, `license`, `allowed-tools`, `compatibility`, `metadata`),
   - the body has an H1 title,
   - all seven required sections are present and non-empty,
   - the manifest is at most 500 lines,
   - any bundled `scripts/`, `references/`, or `assets/` directory is flat.
3. **results** — always runs, depends on the other three, and fails if any of
   them failed or was cancelled. It is designed to be the single required
   status check on `main` so adding or renaming jobs in `pr.yml` doesn't
   require touching branch protection.

Failure output names the exact issue so you can fix and re-push.

## Branch protection on `main`

GitHub branch-protection lives in repo settings, not in the workflow files. The
active configuration for `main` is the ["main" repository ruleset](https://github.com/bcgov/agent-skills/settings/rules/17296594)
(`gh api /repos/bcgov/agent-skills/rulesets/17296594`). At time of writing it
enforces:

- **Pull request required** before merging. Approvals are not required by the
  ruleset (review is by convention), code-owner review is not required, and
  allowed merge methods are squash and merge commit (rebase is disabled).
- **Required status check: `results`** (strict — branch must be up to date with
  `main`). `results` aggregates `fork-gate`, `lint-tests`, and `skills` from
  [.github/workflows/pr.yml](.github/workflows/pr.yml), so requiring just this
  one check means new jobs added to `pr.yml` are picked up automatically with
  no ruleset edit.
- **Signed commits required** on every commit that lands on `main`.
- **Code scanning** (CodeQL via GitHub's default setup, configured in *Settings → Code security*) required at the high-or-higher severity threshold. There is no `codeql.yml` workflow in this repo — the scan is wired in at the repository level, not in `.github/workflows/`.
- **Force-push blocked** (`non_fast_forward`) and **branch deletion blocked**.
- **No bypass** — `bypass_actors` is empty and `current_user_can_bypass` is
  `never`, so even admins land changes through PRs.

If you want CODEOWNERS-based review on top of that, add ownership rules to
[.github/CODEOWNERS](.github/CODEOWNERS) (it currently has no rules) and turn
on "Require review from Code Owners" in the ruleset.

Dependabot is configured in [.github/dependabot.yml](.github/dependabot.yml)
to open daily, grouped PRs for GitHub Actions and Python (uv) dependencies.
Those PRs run through the same PR workflow as any other change, and
[.github/workflows/dependabot-auto-merge.yml](.github/workflows/dependabot-auto-merge.yml)
approves and enables auto-merge for them — so a green Dependabot PR merges
itself once `results` passes, and a Dependabot bump that breaks the validator
stays red until a human fixes it.

## Review expectations

- Keep skills focused — one clear purpose per skill.
- Write descriptions that make it obvious **when** a skill should fire.
- Prefer clarity over cleverness; these are shared across many teams.
- Be responsive to review feedback — most PRs need a small iteration or two.

## Code of conduct

Be respectful, assume good intent, and help fellow contributors. Open an issue
or discussion to propose a new skill before building if you'd like early
feedback.
