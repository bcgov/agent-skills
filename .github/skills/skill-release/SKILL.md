---
name: skill-release
description: Bumps a skill's version and ships it as an npm package when a contributor is ready to release a change.
---

# Skill Release

## Use When
- The user changed a skill and is ready to release it.
- The user asks how versioning or publishing works in this repo.
- The user wants to know whether a version will actually publish on merge.

## Don't Use When
- The user is still authoring a brand-new skill → use `skill-author`.
- The user just wants to check spec compliance → use `skill-validator`.
- The user wants to consume/install a published skill, not release one.

## Workflow
1. Decide the change size: patch (fix/wording), minor (compatible capability), major (breaking).
2. From the skill folder, run `npm version patch|minor|major` to bump `package.json`.
3. Validate with `uv run python scripts/validate_skill.py skills/<name>/SKILL.md`.
4. Open a PR; on merge to `main` the publish workflow reads `name` + `version` and runs `npm publish --tag latest`. The `--tag latest` keeps the `latest` dist-tag pointed at the version this run shipped, so consumers who `npm install @bcgov/skill-<name>` (no version) get the new release.
5. Confirm the release: the workflow skips any version already published, so only a bumped version ships.

## Rules
- Always bump the `version` in `package.json` for any release. (Why: the publish workflow skips already-published versions, so an unbumped merge ships nothing.)
- Always choose the semver level by impact on consumers, not effort. (Why: a tiny but breaking change is still a major; consumers rely on semver ranges to upgrade safely.)
- Never hand-edit a version to one that was already published. (Why: npm registry versions are immutable and the publish will fail.)
- Never bypass the `--tag latest` behaviour for a normal forward release. (Why: the publish script ships every changed skill with `npm publish --tag latest`, which is what makes `npm install @bcgov/skill-<name>` resolve to the newest version. Backport publishes on an older line are the only case that wants a different dist-tag, and they belong in a follow-up `npm dist-tag` step rather than an edit to the publish script.)

## Examples
- "I fixed a typo in the example skill, release it" → `npm version patch`, validate, open PR.
- "This skill now supports a new lookup, ship it" → `npm version minor`, validate, open PR.
- "Why didn't my merge publish anything?" → check whether `version` was bumped; an unchanged version is skipped by design.
- "How do consumers pick up my release without pinning a version?" → `npm install @bcgov/skill-<name>` resolves to the `latest` dist-tag, which the publish workflow updates on every release.

## Edge Cases
- If the user is unsure of the level → ask whether existing consumers would break; if yes it's major, if it only adds it's minor, otherwise patch.
- If `npm publish` fails with a version conflict → the version already exists; bump again to the next unused version.

## References
See [CONTRIBUTING.md](../../../CONTRIBUTING.md) for the `npm version` flow and [README.md](../../../README.md) for how publishing and consumption work end to end.
