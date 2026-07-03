---
name: github-action-consolidation
description: Guide for migrating and consolidating legacy GitHub Actions into the centralized bcgov/actions monorepo.
owner: bcgov
tags: [github-actions, migration, consolidation]
---
# GitHub Action Consolidation

## Use When
- Consolidating a legacy, standalone GitHub Action repository into the `bcgov/actions` monorepo.
- Deprecating and adding deprecation warnings to legacy repositories that have been consolidated.

## Don't Use When
- Implementing or editing the codebase of a Node.js action -> use `github-action-node-authoring`.
- Just refactoring existing actions without moving/decommissioning repositories -> use `github-action-node-authoring`.
- Creating regular application workflow files -> use `github-actions`.

## Critical: Do NOT Use Composite Wrappers
**Never replace a legacy action's codebase with a composite wrapper that delegates via `uses: bcgov/actions/<name>@<tag>`.** This causes GitHub Actions to nest all inner steps under a single collapsed line in the UI, making error logs unreadable for downstream consumers. 

Instead, keep the original working code in the legacy repository and add a deprecation warning. The legacy repo is left as-is (or archived) while the monorepo becomes the home for all new development.

## Workflow
1. **Trace & Understand**: Review the original Bash/JavaScript action to understand its inputs, outputs, and side-effects.
2. **Implement in Monorepo**: Follow the workflow in `github-action-node-authoring` to re-implement or copy the action logic inside a new directory in the monorepo.
3. **Test in Monorepo**: Add a GitHub Actions integration test workflow in the monorepo's `.github/workflows/` (matching the pattern of `test-<action-name>.yml`).
4. **Add Deprecation Warning to Legacy Repo**: Do NOT remove the original code. Add a deprecation notice directly into the main execution path to guarantee it runs everywhere (including the repo's own integration tests and local calls):
   - **Node actions** (`using: node24` or older): Inject the warning directly into the top of the main entry point (e.g. `console.log("::warning::This Action has moved...")` or `info()`).
   - **Composite actions** (`using: composite`): Prepend a warning step to the existing `action.yml` using `echo "::warning::This Action has moved..."`.
5. **Replace Legacy README**: Replace the entire README with a minimal deprecation redirect. Strip all original documentation to force users to the monorepo.
6. **Archive**: Once the deprecation warning and README redirect are in place, archive the legacy repository.

## Rules
- Never create composite wrappers. Keep the original working code in the legacy repo.
- Never strip the legacy codebase. The original action code, tests, and release workflow must remain functional. Only add the deprecation warning on top.
- Always use `vX.Y.Z` style placeholders in documentation instead of hallucinating versions.
- Always frame the deprecation as "moved" so users do not build custom alternatives.
- Always ensure warnings run during main execution. Never use `pre` or `post` hooks in `action.yml` for warnings, as these are ignored during local test runs.

## Examples
- "Migrate action-pr-description-add to the monorepo" -> set up branch in both repos, copy/implement the node action using the authoring skill, add a warning step to legacy repository, replace README with a redirect, and archive it.
- "Deprecate the legacy repository" -> prepend warnings directly to legacy main execution path, replace README with a redirect, and archive.

## Edge Cases
- If the original action uses `runs: using: 'docker'` -> consult the `github-action-node-authoring` skill for details on rewriting container dependencies in Node.
- If there are orphaned CI jobs or dangling dispatch triggers in the old repo -> remove them during the cleanup phase.
- For composite actions with companion files (`action.sh`, `scripts/`) -> these files stay in the legacy repo as-is. Only the deprecation warning step is added to `action.yml`.

## References
- See [skills/github-action-node-authoring/SKILL.md](../github-action-node-authoring/SKILL.md) for action implementation guidelines.
- See [https://github.com/bcgov/actions](https://github.com/bcgov/actions) for the centralized monorepo structure.
