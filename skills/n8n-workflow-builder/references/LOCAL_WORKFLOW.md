# Local workflow — the n8n workflow as a shell script

Every workflow this skill builds also gets a **local equivalent**: a shell script a developer runs
on their machine to fire the same run without n8n. It runs the SAME `tools/n8n/merge.sh` and
`report.sh` as the n8n nodes, so the two stay in lockstep; it writes an HTML report to `/tmp` and
prints a file:// URL.

Start from `assets/local-workflow.sh`, copy it to `tools/n8n/workflows/<name>.local.sh`, and fill
the `<--` markers (group, page name, the collection snippets, the validators, the report(s)).

## n8n node -> shell stage

| n8n node                            | `local-workflow.sh` stage                                 |
| ----------------------------------- | --------------------------------------------------------- |
| Webhook (params)                    | the env the snippets read (inherited by every child)      |
| Execute-Command (one per collect)   | `export MERGE_<KEY>="$(snip <snippet>)"`                  |
| Merge snippets                      | `merge.sh` — flat merge, fields stay top-level            |
| Execute-Command (one per validator) | `export MERGE_<CHECK>="$(snip <validator>)"` (on merged)  |
| Merge validations                   | `merge.sh -k` — keyed by check -> the `.validations` obj  |
| Report                              | `report.sh` — assemble `merged + {validations}`, render   |
| Markdown -> Respond                 | `view.sh` — HTML in `/tmp`, prints a file:// URL          |

The two stay in lockstep: every collection/validator node is one `MERGE_*` line, and the join +
report stages call the same `merge.sh` / `report.sh` the n8n nodes do.

## Merging (merge.sh)

Each collection snippet prints one JSON object; the script exports them as `MERGE_*` and runs
`merge.sh` (flat = `jq -s add`), so fields stay top-level (`.members`, `.connections`, …). `|| true`
keeps a failing step from aborting — its data is just absent, and the `{{#if}}`-guarded report
renders whatever arrived. Validator verdicts are exported as `MERGE_<CHECK>` and merged with
`merge.sh -k` (keyed by check) into the `.validations` object. `unset ${!MERGE_@}` between stages so
the two merges don't bleed into each other.

## Report (report.sh)

`report.sh <group> <report.md>…` takes the merged data and validations (base64 in `DATA` / `VALS`,
matching how the n8n report node passes them), assembles `merged + {validations}`, and renders each
report — chaining each as the next's `.previous`, so the first report arg ends up on top of the page.

## view.sh — Markdown -> HTML -> open

`tools/n8n/view.sh` is the local stand-in for the Markdown + Respond nodes (it is **not** used in
the n8n container — n8n has its own Markdown node):

```bash
report.sh <group> <report.md> | view.sh <name>   # writes /tmp/n8n-report/<name>.html, prints a file:// URL
```

It embeds the rendered Markdown in a small HTML page that styles + renders it with marked.js +
github-markdown-css from a CDN, so no local Markdown tooling is needed.

## Running it

```bash
<ENV>=<value> tools/n8n/workflows/<name>.local.sh   # prints a file:// URL — click to open
```

Read-only and idempotent: safe to re-run any time, like firing the webhook. Shellcheck the
generated `<name>.local.sh` before committing it.
