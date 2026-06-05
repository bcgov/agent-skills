---
name: skill-validator
description: Validates skill profiles against the spec and explains how to fix failures before a PR is opened or merged.
---

# Skill Validator

## Use When
- The user wants to know whether a skill passes the spec.
- A PR check failed and the user needs to understand the error.
- The user is about to open a PR and wants a local pre-flight check.

## Don't Use When
- The user wants to create a new skill from scratch → use `skill-author`.
- The user wants to bump a version or publish → use `skill-release`.
- The failure is a Python/tooling error unrelated to a skill's contents.

## Workflow
1. For one skill, run `uv run python scripts/validate_skill.py skills/<name>/SKILL.md`.
2. For everything, run `uv run python scripts/validate_skill.py --all`.
3. To mirror CI on a branch, run `uv run python scripts/validate_skill.py --base origin/main`.
4. Read each `- <message>` line under a failing file and map it to the offending section or field.
5. Edit the `SKILL.md` or `package.json` to fix it, then re-run until the file shows `✓`.

## Rules
- Always re-run the validator after each fix rather than batching guesses. (Why: one fix can reveal or mask another, and the validator is fast.)
- Always check both the `SKILL.md` and the sibling `package.json` on a failure. (Why: the validator reports manifest and package errors together for the same skill.)
- Never edit `scripts/validate_skill.py` to make a skill pass. (Why: the spec is the contract; loosening the validator weakens every skill in the catalogue.)

## Examples
- "Does my skill pass?" → run the validator on its `SKILL.md` and report ✓ or the exact failures.
- "The PR check says 'missing required section Edge Cases'" → add a non-empty `## Edge Cases` section and re-validate.
- "Validate everything before I push" → run `--all` and summarize the results.

## Edge Cases
- If `--base` finds no changed skills → report that nothing changed; there is nothing to validate.
- If the error is `missing package.json` → create one from `templates/package.json` beside the manifest before re-running.

## References
See [spec/SKILL_SPEC.md](../../../spec/SKILL_SPEC.md) for what each check enforces and [CONTRIBUTING.md](../../../CONTRIBUTING.md) for the PR-check summary.
