---
name: workflow-builder
description: Compose and chain cleaned snippets into n8n operational triage workflows — a webhook trigger, read-only idempotent triage steps in order, and a markdown-to-HTML response served back to the caller. Produces n8n workflow JSON in tools/n8n/workflows/ ready to POST to the n8n API (you post it, not the skill), plus a local_workflow.sh equivalent a developer can run without n8n. Use when building or iterating a triage workflow from cleaned snippets.
owner: Compliance and Enforcement
tags: [n8n, workflow, triage, webhook, automation]
---

# Workflow Builder

Takes **cleaned** snippets (produced by the `runbook-parser` skill) and chains them into an
n8n **workflow JSON** that performs operational triage. The workflow is webhook-triggered and
serves an HTML page of the results, so an operator can click a URL and read the triage report
in a browser.

Every step is **read-only and idempotent** — the cleaned-snippet contract already guarantees
this, and this skill restates it on each node as a second line of defence. No mutating steps
(writes, restarts, restores, schema/config edits) ever go into a triage workflow.

Shape of every workflow this skill builds:

```
[Sticky Note: production URL]   [Webhook (responseMode=responseNode)]
                                          │
        ┌─────────────────────────────────┘
        ▼
  snippet · snippet · …  →  Merge snippets (merge.sh)      (Execute-Command, one per snippet, read-only)
        ▼
  validator · validator · …  →  Merge validations (merge.sh -k)
        ▼
  Report (report.sh) → Respond to Webhook — serves a marked.js page (Content-Type: text/html)
```

It writes the JSON to `tools/n8n/workflows/<name>.json`. It does **not** POST it —
`tools/n8n/push.sh` does that.

Alongside the JSON it emits a **local equivalent** — `tools/n8n/workflows/<name>.local.sh`, the
same chain as a shell script (collect snippets -> merge -> `render.sh` -> `view.sh`) so a
developer can run the triage locally and read the HTML report in a browser, no n8n needed. See
`references/LOCAL_WORKFLOW.md`.

The chain's lib scripts — `merge.sh`, `report.sh`, `render.sh`, `view.sh`, `utils.sh`,
`n8n-entrypoint.sh` — live in this skill under `scripts/` (it owns them; both the n8n image and the
local workflow call them). They self-locate via `$0` and resolve `utils.sh` / `render.sh` /
`snippets/<group>` relative to that location, so they must run from the **triage tree root, alongside
`snippets/`**. `scripts/sync.sh <tree-root>` does exactly that — copies the canonical scripts to the
root (idempotent; `--check` verifies without writing). **When building an n8n image, run it so the
scripts sit beside the Dockerfile** — as committed here in `tools/n8n/`, which the Dockerfile bakes
into `/opt/triage` and `n8n-entrypoint.sh` puts on `PATH`. `scripts/` is canonical (the skill is
installed separately); the local workflow runs `sync.sh` on startup, so a dev always runs the
installed skill's current scripts.

## Use When

- Building an n8n triage workflow by chaining cleaned `snippet-*` blocks from `snippets/<group>/`.
- Iterating on an existing triage workflow (add/remove/re-order steps).
- Producing n8n workflow JSON to hand to `push.sh` / the n8n API.

## Don't Use When

- Cleaning raw snippets into cleaned blocks → use the `runbook-parser` skill (`references/CLEANING.md`).
- Posting or pulling workflow JSON to/from n8n → use `tools/n8n/push.sh` / `pull.sh`.
- Any mutating or non-triage automation → this skill only emits read-only, idempotent triage.

## Workflow

1. Choose the cleaned snippets to chain, in triage order, from `snippets/<group>/`. If none
   exist yet, run the `runbook-parser` cleaning step first.
2. Copy `assets/skeleton.json` as the starting point — it already has the Sticky Note (with
   the production URL placeholder), the Webhook (`responseMode: responseNode`), and the
   Report -> Respond tail.
3. Give every snippet and validator its OWN `n8n-nodes-base.executeCommand` node, one call each: a
   collection node runs `NAMESPACE={{ ($('Webhook').item.json.query||{}).namespace }} snippet-*.sh`;
   a validator node pipes the merged JSON in with
   `echo {{ $('Merge snippets').item.json.stdout.base64Encode() }} | base64 -d | validator-*.sh`.
   Set each node's `notes` to a brief, specific line on what it does (`references/N8N_NODES.md`).
4. Join with `tools/n8n/merge.sh`, never a Code node. A "Merge snippets" node lists one
   `export MERGE_<KEY>={{ $('<collection node>').item.json.stdout.base64Encode() }}` per collection
   node, then `merge.sh --b64` (flat — snippet fields stay top-level). A "Merge
   validations" node does the same over the validator nodes (key = the check name), then
   `merge.sh -k --b64` (keyed -> the `.validations` object).
5. Render with one "Report" node: `export DATA={{ $('Merge snippets').item.json.stdout.base64Encode() }}`,
   `export VALS={{ $('Merge validations').item.json.stdout.base64Encode() }}`, `export NAMESPACE={{ … }}`,
   then `report.sh <group> <report.md> …` — report.sh assembles `merged + {validations}`
   and renders the chained report. End with a single Respond node that serves the report markdown as a
   marked.js + github-markdown-css page (`Content-Type: text/html`) — no Markdown node, identical to
   `view.sh` (see `references/N8N_NODES.md`).
6. Fill the Sticky Note from `assets/sticky-note.md`: substitute `<BASE_URL>` (`config.yaml`
   `spec.n8n.base_url`), `<PATH>` (the Webhook path = workflow name), `<TITLE>`, and `<QUERY>`.
7. Write valid workflow JSON (`name`, `nodes`, `connections`, `settings`) to
   `tools/n8n/workflows/<name>.json` per `references/API_SCHEMA.md`. Do not POST it.
8. Emit the local equivalent: copy `assets/local-workflow.sh` to `tools/n8n/workflows/<name>.local.sh`
   and fill it — it runs the same `merge.sh` / `report.sh`, so local and n8n stay in lockstep, and it
   must pass `shellcheck`. See `references/LOCAL_WORKFLOW.md`.

## Rules

- Every node is read-only and idempotent — the cleaned-snippet contract makes triage safe to fire
  repeatedly from a webhook. Keep `notes` brief and specific to what the node does; don't restate
  read-only/idempotent or repeat boilerplate (a reviewer sees that in the snippet itself).
- Never include a mutating step. If a cleaned snippet is not read-only, it should already be
  dropped upstream; never add one here.
- Always start with a Webhook trigger plus a Sticky Note holding the production URL, built from
  `assets/sticky-note.md` with the host from `config.yaml` `spec.n8n.base_url`
  (`<base_url>/webhook/<workflow-name>`) — never hardcode a host.
- Always end with a Report node (`report.sh`) -> Respond to Webhook that serves the report markdown as
  a marked.js page with `Content-Type: text/html`; the Webhook node `responseMode` must be `responseNode`.
- Emit only the API-writable fields (`name`, `nodes`, `connections`, `settings`); never POST —
  hand the file to `push.sh`.
- Give every node a unique `name` and `id`, and wire `connections` by node name.
- Each snippet and validator is its own one-call Execute-Command node, and the report is one
  `report.sh` node — copy-pasteable, reorderable within their group. Join with `tools/n8n/merge.sh`,
  NEVER a Code node: a "Merge snippets" node (`merge.sh --b64`, flat) and a "Merge validations" node
  (`merge.sh -k --b64`, keyed by check) (Why: transparent + no jsCode reaching into nodes by name).
- Keep each node command short — a snippet/validator call is well under ~200 chars and stays a plain
  JSON string. The exception is a merge/report node whose `export …` block is multi-line and long;
  store THAT command as a JSON array of lines (one element per line) so git diffs stay readable.
  `push.sh` joins the array with `\n` (the string n8n wants); `pull.sh` splits a > 200-char multi-line
  command back to an array — both accept either form. Pass node stdout base64-encoded
  (`{{ $('node').item.json.stdout.base64Encode() }}` + `merge.sh --b64`) so JSON survives the shell.
- n8n node commands call the baked scripts by bare name (`merge.sh`, `report.sh crunchy-triage …`,
  `snippet-*.sh`). The image bakes the triage tree under `/opt/triage` (NOT `/data`, a runtime PVC
  mount that shadows it) and `chmod +x`'s the scripts; the `n8n-entrypoint.sh` wrapper adds
  `/opt/triage` + every baked `snippets/<group>` dir to `PATH` at startup, so any group the team adds
  just works — no per-group Dockerfile edit. (`local-workflow.sh` calls the same scripts as
  `bash "$N8N/…"` from its own location — dev machines have nothing on `PATH`.)
- The lib scripts live in `scripts/` (canonical) and must be deployed to the triage tree root
  alongside `snippets/` to run. `scripts/sync.sh <tree-root>` deploys/verifies them (the local
  workflow runs it on startup; `--check` guards CI). For an n8n image build, run it so the scripts
  sit beside the Dockerfile (committed here as `tools/n8n/*.sh`).
- Emit the `local-workflow.sh` equivalent too — it runs the SAME `merge.sh` / `report.sh`, so local
  and n8n stay in lockstep; it must pass `shellcheck`.
- Shellcheck every `.sh` this skill produces (the `local-workflow.sh`) before signing off; fall
  back to `bash -n` only if shellcheck is unavailable.

## Examples

- "Build a triage workflow from these cleaned blocks" then chain the collection snippets in
  order, end with markdown->HTML->respond, and write `tools/n8n/workflows/<name>.json`.
- "Add another check to the workflow" then insert one Execute-Command node and rewire
  `connections`.
- "Serve the report as a web page" then confirm the Webhook is `responseNode` and the final
  Respond-to-Webhook sets `Content-Type: text/html`.

## Edge Cases

- A snippet emits non-JSON then normalize it in a Code node before chaining.
- No cleaned snippets exist then run the `runbook-parser` cleaning step first.
- The page renders blank then check the Respond node's page got the Report stdout (the base64
  expression resolves) and that `responseMode` is `responseNode`.
- Long-running steps then keep the webhook responsive by chaining quick read-only checks; do
  not block on anything that mutates or waits.

## References

- `references/N8N_NODES.md` — the node JSON for each type (webhook, sticky note,
  execute-command, respond-to-webhook), the merge/report nodes, connections, and the
  serve-HTML (marked.js) pattern.
- `references/API_SCHEMA.md` — the n8n workflow JSON schema to POST (`name`/`nodes`/
  `connections`/`settings`), per the n8n API reference; `push.sh` posts it.
- `assets/skeleton.json` — a minimal, importable workflow (sticky + webhook + collect + merge +
  report + respond) to copy and extend.
- `assets/sticky-note.md` — the standard Sticky Note (Production URL) content; fill `<BASE_URL>`
  from `config.yaml` `spec.n8n.base_url`.
- `assets/local-workflow.sh` — the local-workflow skeleton (the shell equivalent) to copy to
  `tools/n8n/workflows/<name>.local.sh` and fill.
- `scripts/` — the chain's lib scripts (`merge.sh`, `report.sh`, `render.sh`, `view.sh`, `utils.sh`,
  `n8n-entrypoint.sh`) plus `sync.sh`, which deploys/verifies them into a triage tree root alongside
  `snippets/` (the local workflow runs it on startup; `--check` for CI; committed here as `tools/n8n/*.sh`).
- `references/LOCAL_WORKFLOW.md` — the local-workflow mapping (n8n node -> shell stage),
  merging, and the `view.sh` helper.
- `scripts/view.sh` — builds the marked.js + github-markdown-css page for the local workflow; the
  n8n Respond node serves the same page (keep them in sync).
- `../runbook-parser/references/CLEANING.md` — where the cleaned snippets come from.
