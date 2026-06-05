# Contributing to agent-skills

Thanks for helping build BC Gov's shared library of agent skill profiles. This
repository is community-maintained — new skills and improvements to existing
ones are all welcome.

## Before you start: access requirements

This repository is open to **BC Gov GitHub organization members only**.
Contributions from forks outside the organization are not accepted — the PR
workflow has a dedicated `fork-gate` job that fails any pull request opened
from a fork, and branch protection requires that job to pass before merge. A
fork PR therefore cannot go green and cannot merge.

To contribute:

1. **Join the `bcgov` GitHub organization.** If you're not already a member,
   request membership through your team or the BC Gov DevOps onboarding process.
2. **Request write access to this repository.** Maintainers grant write access
   so you can push feature branches and open pull requests directly against this
   repo. You do **not** fork — you branch.

If you can't push a branch to this repository, you don't yet have the access you
need; sort that out before opening a PR.

## How contributions work

All changes are made through pull requests from a branch **in this repository**.
Direct pushes to `main` are not permitted, and PRs from forks are not run.

1. **Branch** — with your granted write access, create a feature branch in this
   repo for your change. (Forks are not supported.)
2. **Add or update a skill** — follow [spec/SKILL_SPEC.md](spec/SKILL_SPEC.md)
   and start from [templates/SKILL.md](templates/SKILL.md) +
   [templates/package.json](templates/package.json).
3. **Bump the version** — if you're changing an existing skill, raise its
   `version` in that skill's `package.json` (see below). New skills start at
   `0.1.0`.
4. **Validate locally** — `uv run python scripts/validate_skill.py skills/<name>/SKILL.md`.
5. **Open a pull request** — describe what the skill does and why it's useful.
6. **Pass the checks** — the PR check validates every changed skill.
7. **Review & merge** — a maintainer reviews; once approved and green, it merges
   and the publish workflow ships the bumped version as an npm package.

## Skill structure

Each skill lives in its own directory. The whole directory is bundled into the
published package, so put everything the skill needs alongside its manifest:

```
skills/<skill-name>/
├── SKILL.md        # required: the manifest
├── package.json    # required: published name + version
├── scripts/        # optional: executable helpers
├── references/     # optional: heavy detail
└── assets/         # optional: templates & resources
```

`SKILL.md` needs mandatory `name` + `description` frontmatter, then a body with
an H1 title and the seven required sections (Use When, Don't Use When, Workflow,
Rules, Examples, Edge Cases, References). `name` must be kebab-case (≤64 chars)
and match the skill's directory name; `description` must be ≤1024 chars with no
angle brackets. Keep the manifest under 500 lines and any `scripts/`,
`references/`, or `assets/` directory flat (one level deep).

`package.json` holds the published package `name` (`@bcgov/skill-<name>`) and
the `version`. **The version lives only here — not in `SKILL.md`** — so there's
one source of truth and no drift. See the spec for the full definition.

## Versioning

Skills are published as npm packages, so use [semver](https://semver.org/) and
bump the version with npm from inside the skill directory:

```bash
cd skills/<your-skill>
npm version patch   # bug fix / wording tweak   → 0.1.0 → 0.1.1
npm version minor   # new capability, compatible → 0.1.1 → 0.2.0
npm version major   # breaking change            → 0.2.0 → 1.0.0
```

The publish workflow **skips any version already published**, so a merge only
ships a release when the version has been bumped.

## Tooling

This project uses [uv](https://docs.astral.sh/uv/) — there is no
`requirements.txt`. Dependencies are declared in `pyproject.toml` and installed
on demand by `uv run`. Common commands:

```bash
make format     # auto-format Python (2-space indent, double quotes)
make lint       # lint Python: style, imports, docstrings, bug patterns
make test       # run the validator unit tests
make validate   # validate every skill
```

Python is formatted and linted with [ruff](https://docs.astral.sh/ruff/),
configured in `pyproject.toml` (2-space indentation, double quotes, and
docstrings required on every function). Run `make format` before pushing.

## PR checks

Pull requests **opened from a branch in this repository** run two real jobs
after a hard fork-gate, plus a final aggregator. PRs opened from a fork fail at
the gate (see access requirements above).

0. **fork-gate** — runs first and fails immediately if the PR's head repo is
   not this repo. This is a real failed status check, not a neutral skip, so
   branch protection can require it.
1. **Codebase** — runs next, because broken tooling makes validating skill
   output meaningless. It checks the code that produces skills:
   - `ruff format --check` — Python is correctly formatted,
   - `ruff check` — lint, import order, and docstring coverage pass,
   - `pytest` — the validator's unit tests pass.
2. **Skills** — runs only after the codebase job passes. It runs
   `scripts/validate_skill.py` against the skills your PR changed and confirms:
   - the frontmatter block exists, is closed, and parses as a mapping,
   - `name` and `description` are present and non-empty,
   - `name` is kebab-case (≤64 chars) and matches the skill's directory name,
   - `description` is ≤1024 chars with no angle brackets,
   - no unexpected frontmatter keys are present,
   - the body has an H1 title,
   - all seven required sections are present and non-empty,
   - the manifest is at most 500 lines,
   - any bundled `scripts/`, `references/`, or `assets/` directory is flat,
   - a `package.json` sits beside the manifest with a valid `name` and a semver
     `version`, and no `files` whitelist (the whole skill folder bundles
     automatically).

A PR cannot merge until both jobs pass. Failure output names the exact issue so
you can fix and re-push.

There is also a fourth job, **results**, that always runs, depends on the
three above, and fails if any of them failed or was cancelled. It exists so
branch protection only has to require **one** status check (see below) —
adding or renaming jobs in the workflow never requires updating branch
protection.

## Maintainer setup

The contribution model above relies on a few one-time settings on the `main`
branch. If you are setting this repository up (or auditing it), confirm all of
these under **Settings → Branches → Branch protection rules → `main`**:

- **Require a pull request before merging.** Direct pushes to `main` are
  blocked; every change goes through a reviewed PR.
- **Require approvals** — at least one maintainer review (use the
  `@bcgov/agent-skills-maintainers` team via [.github/CODEOWNERS](.github/CODEOWNERS)).
- **Require status checks to pass before merging**, and mark exactly one check
  as required:
  - `results` — the aggregator that fails if `fork-gate`, `lint-tests`, or
    `skills` failed or was cancelled. Requiring only this check means new
    jobs added to `pr.yml` are picked up automatically, with no branch-
    protection edit.
- **Require branches to be up to date before merging** — keeps the validator
  run honest by re-running against the latest `main`.
- **Restrict who can push to matching branches** — empty list (everyone goes
  through PRs, including maintainers).
- **Do not allow bypassing the above settings** — even admins land changes
  through PRs.

Dependabot PRs run through the same gates, which is exactly what we want: a
supply-chain bump that breaks the validator stays red until a human fixes it.

## Review expectations

- Keep skills focused — one clear purpose per skill.
- Write descriptions that make it obvious **when** a skill should fire.
- Prefer clarity over cleverness; these are shared across many teams.
- Be responsive to review feedback — most PRs need a small iteration or two.

## Code of conduct

Be respectful, assume good intent, and help fellow contributors. Open an issue
or discussion to propose a new skill before building if you'd like early
feedback.
