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
- The failure is a Python/tooling error unrelated to a skill's contents.

## Workflow
1. For one skill, run `uv run python scripts/validate_skill.py skills/<name>/SKILL.md`.
2. For everything, run `uv run python scripts/validate_skill.py --all`.
3. To mirror CI on a branch, run `uv run python scripts/validate_skill.py --base origin/main`.
4. Read each `- <message>` line under a failing file and map it to the offending section or field.
5. Edit the `SKILL.md` to fix it, then re-run until the file shows `✓`.

## Rules
- Always re-run the validator after each fix rather than batching guesses. (Why: one fix can reveal or mask another, and the validator is fast.)
- Never edit `scripts/validate_skill.py` to make a skill pass. (Why: the spec is the contract; loosening the validator weakens every skill in the catalogue.)

## Examples
- "Does my skill pass?" → run the validator on its `SKILL.md` and report ✓ or the exact failures.
- "The PR check says 'missing required section Edge Cases'" → add a non-empty `## Edge Cases` section and re-validate.
- "Validate everything before I push" → run `--all` and summarize the results.

## Edge Cases
- If `--base` finds no changed skills → report that nothing changed; there is nothing to validate.
- If the error names a missing or empty section → add the section heading (verbatim) with at least one bullet of content and re-run.

## References
See [spec/SKILL_SPEC.md](../../../spec/SKILL_SPEC.md) for what each check enforces and [CONTRIBUTING.md](../../../CONTRIBUTING.md) for the PR-check summary.
