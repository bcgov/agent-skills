---
name: github-action-consolidation
description: Guide for migrating and consolidating legacy GitHub Actions into the centralized bcgov/actions monorepo.
owner: bcgov
tags: [github-actions, migration, consolidation]
---
# GitHub Action Consolidation

## Use When
- Consolidating a legacy, standalone GitHub Action repository into the `bcgov/actions` monorepo.
- Refactoring older Bash-based actions to Node.js during the migration.
- Creating a composite wrapper in a deprecated repository to point to the new, centralized location.

## Don't Use When
- Updating an action already inside the `bcgov/actions` monorepo.
- Just fixing bugs or adding minor features without migrating the repository.

## Workflow
1. **Trace & Understand**: Review the original Bash/JavaScript action to understand its inputs, outputs, and side-effects.
2. **Port to Node.js**: Re-implement the action logic inside a new directory in the `bcgov/actions` monorepo using standard Node.js (v20 or v24). Write `index.js`, `action.yml`, and `README.md`.
3. **Test in Monorepo**: Add comprehensive GitHub Actions integration tests for the new action in the monorepo's workflows.
4. **Create Wrapper**: In the legacy repository, replace the original action with a composite wrapper (`action.yml`) that uses the new action via `bcgov/actions/<action-name>@v<version>`. Ensure all inputs are forwarded.
5. **Add Deprecation Warnings**: Add a `::warning::This Action has moved to bcgov/actions/<action-name>` warning to the wrapper action. Do NOT use the word "deprecated" loosely, frame it as "moved".
6. **Cleanup Legacy Repo**: Remove obsolete files (e.g., `index.js`, `action.sh`, tests) in the legacy repo. Empty out the README and provide a prominent link to the new repository.

## Rules
- Always use `vX.Y.Z` style placeholders in documentation instead of hallucinating versions.
- Always branch from `main` and submit PRs back to `main`.
- Always frame the deprecation as "moved" so users do not build custom alternatives.
- Always use explicit `unset GITHUB_TOKEN` before running `gh` commands in the terminal if token issues arise.
- Never run commands without testing them locally. Stop on the first error.
- Never downgrade strict TypeScript flags when writing node equivalents.

## Examples
- "Migrate action-get-pr to the bcgov monorepo" → Re-implement in `bcgov/actions/get-pr`, update `test-get-pr.yml`, then replace `bcgov/action-get-pr` with a composite wrapper pointing to `bcgov/actions/get-pr@v0.2.0`.
- "Deprecate the old repo" → Empty the README and say "This Action has moved to bcgov/actions/get-pr. Please update your workflows."

## Edge Cases
- If the original action uses `runs: using: 'docker'`, ensure the new Node implementation can replicate the containerized dependencies or rewrite them using standard GitHub Actions toolkit methods.
- If there are orphaned CI jobs or dangling dispatch triggers in the old repo, remove them during the cleanup phase.

## References
See [https://github.com/bcgov/actions](https://github.com/bcgov/actions) for the centralized monorepo structure and existing Node.js patterns.
