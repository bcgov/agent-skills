---
name: github-action-node-authoring
description: Standards and guidelines for authoring and refactoring GitHub Actions in Node.js (v24), Vitest, and ESLint flat config.
owner: bcgov
tags: [github-actions, node, javascript, typescript]
---

# GitHub Action Node Authoring

## Use When
- Creating a new custom GitHub Action.
- Refactoring an existing Bash-based or Python-based GitHub Action to Node.js.
- Enhancing or editing an existing Node-based GitHub Action.
- Setting up the test suite (Vitest) or build tool (ncc) for a Node action.

## Don't Use When
- Consolidating/decommissioning legacy repositories -> use `github-action-consolidation`.
- Configuring standard workflows that consume actions -> use `github-actions`.
- Deploying containers to OpenShift -> use `openshift-deployment`.

## Workflow
1. **Initialize Project**: Create the action folder with `package.json`, `action.yml`, `eslint.config.js`, `.knip.json`, `src/`, and `tests/`.
2. **Define inputs/outputs**: Write the `action.yml` manifest using `runs.using: "node24"` and pointing to `dist/index.js` as the main entry point.
3. **Configure Dependencies**: Set up `package.json` with `"type": "module"`, `"engines": { "node": "^24.0.0" }`, and dependencies including `@actions/core`, `@actions/github`, `@vercel/ncc`, and `vitest`.
4. **Implement Core Logic**: Write code in `src/index.js` (or `src/main.ts` if using TypeScript). Leverage official Actions toolkit packages to interact with the environment.
5. **Add Flat Config Linting**: Use ESLint flat configuration (`eslint.config.js`) to enforce formatting and security rules.
6. **Implement Unit Tests**: Write unit tests in `tests/` utilizing Vitest. Mock external resources, the GitHub filesystem, and core action inputs where necessary.
7. **Compile the Action**: Run `ncc build src/index.js -o dist --minify` to compile dependencies and code into a single file `dist/index.js`.
8. **Un-ignore and stage dist**: Ensure the action folder's `dist/` is un-ignored in the root `.gitignore` (using `!path/to/dist/`), stage all files, and run tests locally via `vitest run`.

## Rules
- Always use Node.js (v24) for complex action logic. Never write complex string parsing or API queries in Bash. (Why: Node.js provides a robust, type-safe environment, proper JSON parsing, and testability that Bash lacks, preventing runtime script injections).
- Always include unit tests with Vitest for new or refactored Node actions. Never commit untested JS/TS logic. (Why: Actions run in critical CI paths and errors block deployment; local vitest unit tests catch bugs in milliseconds).
- Always compile the action into `dist/` using `@vercel/ncc`. Never point `action.yml` directly to `src/index.js`. (Why: GitHub Actions runner does not run `npm install` on the action's dependencies at runtime; compiling bundles everything into a single file).
- Always ensure `dist/` is un-ignored in the repository's `.gitignore` and committed. (Why: If `dist/index.js` is ignored by git, the runner will fail with a file not found error when downstream workflows invoke the action).
- Always default missing configurations or environments to production mode rather than testing or development mode. (Why: Prevents accidental deployment of test configurations in production environments).

## Examples
- "Help me port a bash action to Node" -> set up package.json with node24, vitest, and create the src/index.js file.
- "How do I test my new javascript action?" -> write a test file in tests/ using vitest and mock the @actions/core inputs.
- "Let's compile our typescript action" -> run ncc build to compile src/main.ts into dist/index.js and verify it is tracked in git.

## Edge Cases
- If using TypeScript -> ensure tsconfig.json has `"strict": true` and `"noImplicitAny": true`, and compile using ncc directly.
- If dependencies cannot be bundled by ncc -> document exception in README.md and verify the bundle executes without runtime import failures.
- If the project requires binary tools -> wrap execution safely with child_process and ensure error states are caught and reported via `core.setFailed`.

## References
- See [@actions/core](https://www.npmjs.com/package/@actions/core) for standard input, output, logging, and status API controls.
- See [GitHub Actions Toolkit](https://github.com/actions/toolkit) for official developer guides and best practices.
