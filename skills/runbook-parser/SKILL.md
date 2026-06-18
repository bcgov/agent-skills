---
name: runbook-parser
description: Tangle code out of prose runbooks and wikis into version-controlled snippets, per source and losslessly, and detect doc/code drift. Use it to author or extend a RunbookParser config.yaml, run the parser (ingest, check, seal, diff), turn raw snippets into safe parameterized building blocks for n8n, or backport a snippet fix to the source doc.
owner: Compliance and Enforcement
tags: [n8n, runbook, parser, drift, docs-as-code]
---

# Runbook Parser

Turns operational runbook documents (wiki pages, markdown like `crunchy-notes.md`)
into a version-controlled, composable library of building blocks for n8n workflows, and
keeps the extracted code aligned with its source, surfacing drift so fixes can be ported back.

Two kinds of snippet:

- **Raw** (`working_dir/<group>/`) — the parser losslessly decomposes each source into
  ordered, typed snippets named `<source-name>_<section>.ext` (prose to `.md`, fenced blocks
  to `.sh`/`.yaml`/`.sql`/…). Mostly useless alone, but recombining them reproduces the doc,
  which powers drift detection.
- **Cleaned** (`snippets/<group>/`) — you (the agent) rewrite chosen raw snippets into
  `snippet-*` building blocks that are individually runnable, parameterized, read-only and
  idempotent.

`config.yaml` is the single manifest, shaped like a CRD: `spec:` is human-authored,
`status:` is machine-owned and written back by the parser. The tool is a small Python
package at `scripts/parser.py` (requires PyYAML and markdown-it-py); the markdown templating
helper is `tools/n8n/render.sh`.

## Use When

- Authoring or extending a `RunbookParser` `config.yaml` (new sources, merging same-name
  groups). See `references/CONFIG.md`.
- Pulling a wiki or markdown runbook into committed snippets under `snippets/`.
- Turning raw snippets into safe, parameterized cleaned `snippet-*` blocks.
- Checking drift between docs and extracted code (local or CI).
- Backporting a cleaned fix: when the seal breaks, `diff` shows the change and the agent proposes the doc edit.
- Adding a hand-authored cleaned snippet (no raw to start from) and sealing it in one step — `include`.
- Running the parser against another team's repo (each repo has its own config).

## Don't Use When

- Pushing or pulling the n8n workflow JSON itself, use `tools/n8n/pull.sh` / `push.sh`.
- Hand-editing generated raw snippets, edit the source doc and re-run `ingest` instead
  (the parser prunes and overwrites them).
- Plain markdown authoring with no extraction, drift, or composition need.

## Workflow

Forward (doc to raw snippets to cleaned blocks):

1. Locate or create `config.yaml`; confirm `root`, `destination`, `working_dir`.
2. For each source set exactly one of `url:` / `file:`, a `description`, and an optional
   `doc:`; group related sources by a shared `name`.
3. `python scripts/parser.py ingest --dry-run` — review the planned files.
4. `python scripts/parser.py ingest` — materializes raws (and a verbatim copy of each source
   doc) to `working_dir`, and rewrites `status`.
5. `python scripts/parser.py check` — gate on exit 2 (drift) before committing.
6. Clean a source (your judgement, not the parser): pick a source by its unique `name`; its
   `description` is your guidance — what to produce and what to skip (e.g. read-only triage
   collection, not destructive PITR). Read its raw `working_dir/<group>/<name>_*` files and write
   `snippet-*` to `snippets/<group>/` per `references/CLEANING.md` — individually runnable,
   parameterized, read-only and idempotent (harvest inline code from the `.md` too); run the
   linter (`shellcheck` for sh); skip a raw snippet that cannot be made safe and idempotent
   (add it to the group's `skipped` list with a reason in `status`); list what you produce
   under the group's `cleaned`. Also produce `validator-*` checks over the collected data
   (validation separate from fetching; see `references/CLEANING.md`).
7. `python scripts/parser.py seal --source <name>` records the content seal (the source doc
   plus your cleaned snippets, comments excluded) into `status` — the baseline `check` uses to
   flag later snippet-code edits for backport.
8. Commit `snippets/` and `config.yaml`.

Reverse (back-port a fix — `check`/`diff` flag it via the seal):

1. A dev edits a `snippet-*`; `check` reports `SNIPPET CODE DRIFT` (the seal no longer matches).
2. `python scripts/parser.py diff --source <name>` shows the change against the seal snapshot;
   read it with the source doc and propose the doc edit carrying the substantive fix back
   (cleaned -> raw is lossy, so this is judgement, not a mechanical reverse).
3. Apply it to the source doc/wiki, then re-`ingest` and re-`seal`. See `references/BACKPORT.md`.

## Rules

- Always run `ingest` then `check` before committing; never commit with `check` at exit 2.
- Always set exactly one of `url:` / `file:` per source (Why: a source with neither is a
  placeholder that yields no snippets).
- Never hand-edit raw snippets or the parser-owned `status` fields — they are
  regenerated (Why: `ingest` prunes and overwrites them).
- Never promote a mutating or non-idempotent snippet; drop it and record why (Why: cleaned
  blocks must be safe to re-run in any order an n8n workflow composes them).
- Clean a snippet to ONLY the product(s) its source's `description` names; never assume another
  product's labels/CRDs/pods (e.g. a general Postgres snippet must not hardcode a Crunchy operator
  label). Parameterize the target instead — e.g. `POD` / `SELECTOR` for pod selection — so the caller
  supplies it; the workflow that knows the product passes the value. Depend on a second product only
  when that source's `description` documents it (Why: otherwise snippets bleed across products — a
  "postgres" snippet silently needs Crunchy).
- Account for inline code (backtick spans) in the `.md` snippets when cleaning, not just
  fenced blocks.
- Prefer processable output; use JSON via `jq` for verbose or structured data, plain
  stdout otherwise — use judgement.
- Keep logic in readable bash, not big jq strings: use `jq` to extract values and assemble the
  final JSON (`jq -n`), and branch / build messages in plain bash `if`/`else` (or SQL for
  queries). Easier to read and debug.
- Run the language-appropriate linter on every cleaned snippet you produce.
- Start cleaned snippets from `assets/snippet-template.sh` / `assets/report-template.md` (the
  standard header); name them `snippet<sep>…` where `<sep>` matches the rest of the filename's
  style (`snippet-` for kebab, `snippet_` for snake); keep each under 100 lines (ideally 30–60).
- Every snippet uses Unix (LF) line endings — no carriage returns; strip with `tr -d '\r'` if
  your editor adds them (the parser writes LF).
- After cleaning a source, run `seal` to record its baseline; `check` then flags a later edit
  to a cleaned command (not comments) or the source doc as snippet-code drift to backport.
- A hand-authored snippet (one you wrote, not produced from a raw) is brought in with
  `include --source <name> --snippet <file>` — it records the snippet under that source's
  `cleaned` and seals. For a snippet with no source doc, target a placeholder source (no
  url/file); the seal then covers the snippet alone.
- A `validator-<kebab>.sh` checks collection output, not the cluster: it reads the merged JSON on
  stdin, tolerates missing data (`status: "skip"`), and emits `{check, status, message, docs,
  sources}`; the report shows it by its section. Extract with `jq`, decide with plain bash (per
  the rule above). Keep validation separate from fetching; start from `assets/validator-template.sh`.
- Validators link official docs via the shim, never a hardcoded URL: resolve with
  `doc_url <aspect> <version>` (from the group's sibling shim) and list the object(s) checked in
  `sources`. To change a link, edit `config.yaml` `status.docs.topics[]`, run `scripts/doc_links.py`
  to prune dead URLs, then `scripts/doc-link.sh` to regenerate and commit
  `snippets/<group>/<group>.sh` (Why: URLs stay maintainable and travel with the snippets,
  resolving with no yq/config at run time).
- Markdown report snippets list their expected input keys in the header, and guard each data
  section with `{{#if}}` so they degrade gracefully when inputs are absent; `skipped` reasons
  are one sentence.
- Back-port by proposing a doc edit from the `diff` output (cleaned -> raw is lossy; there is no
  automatic reverse); keep the doc canonical, never edit the doc and the snippet separately, and
  re-`seal` after.
- Keep the `working_dir` fetch cache out of commits.
- The parser needs `pip install pyyaml markdown-it-py` (runs locally or in CI, not in n8n).

## Examples

- "Pull the crunchy DR commands from the wiki into snippets" then set the source `url:` and
  run `ingest`.
- "Has our runbook drifted from the docs?" then run `check` and read the unified diff.
- "Add the postgres triage snippets to the same group" then add a same-`name` source and
  re-run `ingest` (auto-merged).
- "Clean the crunchy-dr-wiki source" then read its `description` + raw `working_dir/…` files, write
  read-only `snippet-*` blocks to `snippets/crunchy-triage/`, skip the destructive ones (into
  the group's `skipped` list), and run `shellcheck`.
- "I fixed the pod selector in the snippet, update the doc" then `diff` shows the change;
  propose the doc edit, apply it, and re-`ingest`/`seal`.
- "Show three chained results to the user" then write a markdown `snippet-*` with
  `{{ .json.path }}` and render it with `render.sh`.

## Edge Cases

- Source URL unreachable then the parser falls back to the `working_dir` cache with a
  warning.
- A `doc:` mirror that does not exist then `check` just notes it (no error); the seal already
  covers doc drift, so the mirror is optional.
- Same `name` across sources then snippets merge deterministically in config order.
- A source with neither `url` nor `file` then it is a placeholder contributing nothing.
- A null timestamp then the drift check still runs (null never suppresses it).
- Back-porting into a `url:` source then the agent proposes the doc edit and you paste it into
  the wiki by hand (a remote wiki cannot be pushed to).
- A cleaned command edited after sealing then `check` reports `SNIPPET CODE DRIFT` (a
  comment-only edit does not); run `diff`, propose the doc edit, then re-`seal`.

## References

- `references/CONFIG.md` — every `spec`/`status` field, the merge rule, and the drift
  round-trip model.
- `references/PARSER_USAGE.md` — CLI, subcommands, exit codes, cache, URL normalization, and
  a no-network smoke test.
- `references/CLEANING.md` — the cleaned contract: safety/idempotency/parameterization
  rules, inline-code harvest, linters, and the `render.sh` placeholder syntax.
- `references/BACKPORT.md` — the back-port flow: `diff` surfaces a dev's cleaned change and the
  agent proposes the doc edit.
- `assets/snippet-template.sh` / `assets/report-template.md` — the standard header for
  cleaned bash / markdown report snippets.
- `assets/validator-template.sh` — the standard validator: a read-only check over collected JSON
  that emits an ok/warn/error/skip verdict with a docs link and the objects it checked.
- `scripts/doc_links.py` — validate + prune the doc-link registry (`status.docs.topics`),
  following redirects; removes only URLs that are gone (404/410).
- `scripts/doc-link.sh` + `assets/doc-urls.template.sh` — generate each group's static doc-link
  shim `snippets/<group>/<group>.sh` (the `aspect|version -> url` table) from the registry; a
  group's validators source it (a sibling), so URLs resolve with no yq/config at run time.
- `tools/n8n/utils.sh` — standard shell messaging (info/warn/err/die/have) sourced by validators
  and the n8n helpers.
- `references/SKILL_SPEC.md` — the SKILL.md manifest spec this file conforms to.
