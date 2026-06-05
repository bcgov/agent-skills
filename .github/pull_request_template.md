<!--
  Thanks for contributing a skill! Fill in the sections below so reviewers can
  evaluate quickly. Delete any section that doesn't apply.
-->

## What this PR changes

<!-- One or two sentences. Link the skill: skills/<name>/SKILL.md -->

## Why

<!-- Who needs this and what problem does it solve? When should an agent fire it? -->

## Checklist

- [ ] Followed [spec/SKILL_SPEC.md](../spec/SKILL_SPEC.md) (7 sections, ≤500 lines, kebab-case name, flat resource dirs).
- [ ] Bumped the skill's `version` in `skills/<name>/package.json` (semver — patch / minor / major).
- [ ] Updated `SKILL.md` when behaviour changed (description, Use When, Workflow, Examples).
- [ ] Ran `make validate` (or `uv run python scripts/validate_skill.py skills/<name>/SKILL.md`) locally and it passed.
- [ ] Ran `make format` and `make lint` if Python under `scripts/` or `tests/` changed.
- [ ] Confirmed no secrets, tokens, or credentials are committed.

## Notes for reviewers

<!-- Anything reviewers should know: tradeoffs, alternatives considered, follow-ups. -->
