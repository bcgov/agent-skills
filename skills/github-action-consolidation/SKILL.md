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
- Adding deprecation warnings to legacy repositories that have been consolidated.

## Don't Use When
- Updating an action already inside the `bcgov/actions` monorepo.
- Just fixing bugs or adding minor features without migrating the repository.

## Critical: Do NOT Use Composite Wrappers

**Never replace a legacy action's codebase with a composite wrapper that delegates via `uses: bcgov/actions/<name>@<tag>`.** This causes GitHub Actions to nest all inner steps under a single collapsed line in the UI, making error logs unreadable for downstream consumers. At scale (hundreds of repos on auto-update), this silently degrades the debugging experience for every team.

Instead, keep the original working code in the legacy repository and add a deprecation warning. The legacy repo is left as-is (or archived) while the monorepo becomes the home for all new development.

## Workflow
1. **Trace & Understand**: Review the original Bash/JavaScript action to understand its inputs, outputs, and side-effects.
2. **Port to Node.js**: Re-implement the action logic inside a new directory in the `bcgov/actions` monorepo using Node.js (v24). Write `index.js`, `action.yml`, and `README.md`.
3. **Test in Monorepo**: Add GitHub Actions integration tests for the new action in the monorepo's workflows.
4. **Add Deprecation Warning to Legacy Repo**: Do NOT remove the original code. Add a deprecation notice appropriate to the action type:
   - **Node actions** (`using: node24`): Create a `pre.js` file that emits a `::warning::` workflow command, and add `pre: "pre.js"` to `action.yml`. The `pre` step runs flat in the UI (no nesting). Use raw `process.stdout.write()` — do not depend on `@actions/core` since `pre.js` runs outside the ncc bundle.
   - **Composite actions** (`using: composite`): Prepend a warning step to the existing `action.yml`:
     ```yaml
     - name: Migration Warning
       shell: bash
       run: |
         echo "::warning::This Action has moved to bcgov/actions/<name>. Please update your workflow."
     ```
5. **Replace Legacy README**: Replace the entire README with a minimal deprecation redirect. Strip all original documentation — this forces users to the monorepo for help, which accelerates migration. Use this template:
   ```markdown
   # <Action Name> (Moved)

   > [!IMPORTANT]
   > **This Action has moved!**
   >
   > Development and maintenance of this action are now centralized in the main [bcgov/actions](https://github.com/bcgov/actions) repository under the [<action-dir>](https://github.com/bcgov/actions/tree/main/<action-dir>) folder.
   >
   > Please update your workflows to point to the new location:
   > ```yaml
   > - uses: bcgov/actions/<action-dir>@vX.Y.Z
   > ```
   ```
6. **Archive**: Once the deprecation warning and README redirect are in place, archive the legacy repository. Archived repos still resolve for `uses:` references — downstream workflows keep working with the last known good code. Teams migrate when they want updates.

## Rules
- **Never create composite wrappers.** Keep the original working code in the legacy repo. See the "Critical" section above.
- **Never strip the legacy codebase.** The original action code, tests, and release workflow must remain functional. Only add the deprecation warning on top.
- Always use `vX.Y.Z` style placeholders in documentation instead of hallucinating versions.
- Always branch from `main` and submit PRs back to `main`.
- Always frame the deprecation as "moved" so users do not build custom alternatives.
- Always use explicit `unset GITHUB_TOKEN` before running `gh` commands in the terminal if token issues arise.
- Never run commands without testing them locally. Stop on the first error.
- Never downgrade strict TypeScript flags when writing node equivalents.
- The `pre` field in `action.yml` only executes for remote action references (`uses: org/repo@tag`), not local (`uses: ./`). This is expected — the action's own CI tests won't show the warning, but downstream consumers will.

## Examples
- "Migrate action-pr-description-add to the monorepo" → Re-implement in `bcgov/actions/pr-description-add`, add tests, then in the legacy repo: add `pre.js` deprecation warning + `pre: "pre.js"` to `action.yml`. Do NOT replace the codebase with a wrapper.
- "Deprecate the old repo" → Add deprecation warning, replace README with redirect notice, archive the repository.

## Edge Cases
- If the original action uses `runs: using: 'docker'`, ensure the new Node implementation can replicate the containerized dependencies or rewrite them using standard GitHub Actions toolkit methods.
- If there are orphaned CI jobs or dangling dispatch triggers in the old repo, remove them during the cleanup phase.
- For composite actions with companion files (`action.sh`, `scripts/`), these files stay in the legacy repo as-is. Only the deprecation warning step is added.

## References
See [https://github.com/bcgov/actions](https://github.com/bcgov/actions) for the centralized monorepo structure and existing Node.js patterns.
