---
name: pr-review
description: Line-by-line verification workflow for GitHub Pull Request feedback and automated bot reviews. Enforces mandatory local code inspection, N-item checklist creation, and empirical evidence validation before accepting or rejecting comments. Use when reviewing PR feedback, triaging linter or CodeRabbit comments, or preparing a PR for merge.
owner: bcgov
tags: [pr-review, github, code-review, ci, devops, bcgov, quality]
---

# GitHub PR Feedback & Line-by-Line Review

Structured verification workflow for processing PR feedback, inline code review comments, and automated review bot outputs (e.g. CodeRabbit, Dependabot, ESLint) without taking shortcuts or making unverified assumptions.

## Use When
- Asked to "review PR feedback", "check PR comments", "triage review comments", or "evaluate CodeRabbit feedback".
- Resolving inline PR comments before merging a pull request.
- Verifying code changes against reviewer feedback on GitHub PRs.

## Don't Use When
- Authoring or hardening GitHub Actions workflow YAML files — use [`github-actions`](../github-actions/SKILL.md).
- Running repository maturity scorecards or compliance reviews — use [`github-repo-setup`](../github-repo-setup/SKILL.md).
- Performing high-level security architecture reviews without an active PR.

## Workflow

1. **Fetch Inline Comments**: Query GitHub API for inline review comments on the target PR:
   ```bash
   unset GITHUB_TOKEN && gh api repos/{owner}/{repo}/pulls/{pr_number}/comments
   ```
   Also check general PR review status:
   ```bash
   unset GITHUB_TOKEN && gh pr view {pr_number} --comments
   ```

2. **Inventory and Count ($N$)**: Extract all inline comments from the API payload. Count the total number of feedback items ($N$).
   - If $N = 0$, verify there are no unresolved review threads and report clean PR status.
   - If $N > 0$, enumerate items from $1$ to $N$.

3. **Inspect Local Files at Target Lines**: For every item $1..N$, read the local file around the target line number ($L \pm 5$) using file viewing tools.
   - NEVER evaluate or reject a comment without loading the target local file lines into active context.
   - Compare the reviewer's suggested code against the current local implementation.

4. **Build the Verification Matrix**: Construct a Markdown verification table listing all $1..N$ items:

   | Index | File & Line | Author | Feedback Summary | Local Code Snippet | Status & Action |
   | :---: | :--- | :--- | :--- | :--- | :--- |
   | **1** | `src/foo.ts:42` | `@coderabbitai` | Null check missing on query output | `const res = query();` | **FIXED** — Added `if (!res) throw ...` |

5. **Validate and Apply Fixes**:
   - **Valid Feedback:** Implement minimal, clean code fixes targeting only the specified logic path.
   - **Invalid / False Positive Feedback:** Refute the comment using explicit, line-level code evidence. Never dismiss a comment based solely on sender identity or automated bot status.

6. **Verify and Re-test**: Run local tests, builds, or linting to verify that fixes compile cleanly without introducing regressions:
   ```bash
   npm test && npm run build
   ```
   Commit and push resolved changes cleanly with Conventional Commits.

## Rules

- **Zero Unverified Dismissals**: Never reject or dismiss a review comment based on author identity or automated bot status. Every decision must be justified by code evidence.
- **Mandatory Local Context**: Must view the target local file around line $L \pm 5$ before forming an evaluation.
- **Minimal Scoped Fixes**: Limit code changes strictly to the active PR feedback items. Do not bundle unrequested refactors or style overhauls.
- **Fail Fast on Ambiguity**: If a review comment or test failure is ambiguous, stop and report the exact diff/log to the maintainer before mutating code.

## Examples

### Example 1: Triaging CodeRabbit Bot Comments
**Prompt**: "Review PR #20 feedback"
**Process**: Run `gh api` → find 3 comments on `config/ai/instructions.md` → load local lines via `view_file` → build 3-item matrix → patch valid logic errors → commit & push.
**Output**: 3-item verification table with explicit code receipts for each item.

### Example 2: Clean PR Verification
**Prompt**: "Check PR #15 review status"
**Process**: Query `gh api` → $N = 0$ inline comments → run `gh pr view 15 --comments` → confirm all checks green → report PR ready for merge.
**Output**: Clean PR verification summary.

## Edge Cases

- **Large PRs ($N > 20$ comments)**: Process in batches of 5 items. Complete verification tables per batch before applying code changes.
- **Outdated Comments**: Comments targeting deleted lines or older commits — verify current line contents; if already resolved, mark as **RESOLVED IN PREVIOUS COMMIT** with commit SHA evidence.
- **GitHub API Unavailable / Unauthenticated**: Run `unset GITHUB_TOKEN` to fall back to local keychain credentials. If still unauthorized, prompt for `gh auth login`.

## References

- [GitHub API Pull Requests Reference](https://docs.github.com/en/rest/pulls/comments) — REST API endpoints for PR review comments.
- [GitHub CLI Manual](https://cli.github.com/manual/gh_api) — `gh api` usage and authentication options.
- [github-actions SKILL](../github-actions/SKILL.md) — CI status checks and workflow verification rules.
