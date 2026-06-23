# Cleaning raw snippets into cleaned blocks

**Raw** snippets (under `working_dir/<group>/`) are the verbatim, 1:1 decomposition of a
document — mostly useless on their own, but we keep their parts. **Cleaned** snippets are the
safe, composable subset you (the agent) write to `snippets/<group>/` (no subfolder), where an
n8n workflow can drop one in and chain it.

This is entirely your judgement: read the raw `working_dir/<group>/<name>_<section>.*` files and
write the cleaned `snippet-*` yourself. The parser does not generate or scaffold cleaned
snippets — it only preserves your `cleaned` outcome in `status`.

## Targeting a source + the description prompt

You clean **one source at a time**, picked by its unique `name`. That source's `description`
in `config.yaml` is your prompt — it says what cleaned snippets to produce and, by omission,
what to skip. Example: a description asking to "fetch and collect triage information" means
produce read-only collection blocks; destructive raws (PITR, `patronictl reinit`, restores)
are **skipped** because they are not read-only and the description does not ask for them.

- **Inputs:** the source's `description` + its raw files (`working_dir/<group>/<name>_<section>.*`).
- **Output:** cleaned `snippet-*` in `snippets/<group>/`, and in `status` a `cleaned` list (the
  blocks you produced) plus a `skipped` list (raws you left, each with a reason).

## The contract

A cleaned `snippet-*` MUST be:

1. **Individually runnable** — self-contained, with a shebang and `set -euo pipefail` for
   shell. It must not depend on variables a previous raw line happened to set.
2. **Parameterized** — inputs come from **CLI args and/or env vars**, never hardcoded
   cluster names, namespaces, timestamps, or pod ids. Document each parameter in a header
   comment; fail fast on a missing required one (`: "${NAMESPACE:?set NAMESPACE}"`).
3. **Read-only and idempotent** — safe to run repeatedly, in any order, with no adverse
   mutation or side effect. Observation only.
4. **Processable output** — emit something a downstream snippet can consume. Use **JSON via
   `jq`** for verbose or structured data; plain stdout is fine for a single value. Use
   judgement — not everything needs JSON.

It must also:

5. **Harvest inline code** — when cleaning, look at the inline backtick spans in the raw
   `.md` snippets too (e.g. crunchy's inline `pg_dump …`, `oc apply …`), not just fenced
   blocks.
6. **Pass its linter** — run the language-appropriate linter on every block you produce:
   `shellcheck` for `.sh`, and whatever is available for other languages. Fix what it flags.

## Conventions

- **Start from a template** — `assets/snippet-template.sh` (bash) or `assets/report-template.md`
  (markdown). They fix the standard header comment; keep its shape.
- **Name** `snippet<sep>…<ext>` — the `snippet` prefix takes the **same separator as the rest
  of the filename**, not a fixed one: `snippet-cluster-status` when names are kebab (our style),
  `snippet_cluster_status` if a team uses snake_case. Match the file; be consistent.
- **Size** — keep each snippet **under 100 lines, ideally 30–60**. Split a big collector into
  focused, composable blocks rather than one monolith.
- **Unix line endings (LF)** — no carriage returns in any snippet; a `\r` in a `#!/usr/bin/env
  bash` shebang line breaks execution. The parser writes LF, so yours must too — strip CRLF if
  your editor adds it: `tr -d '\r' < f > f.tmp && mv f.tmp f`.
- **Markdown report snippets declare their inputs** — the header comment lists the keys the
  template expects (`${VAR}` from env/args, `.json.path` from named upstream snippets), so a
  workflow knows what to feed it.
- **Markdown report snippets degrade gracefully** — guard each data section with `{{#if}}` so
  the report renders only what is present and never shows an orphan heading, empty table, or
  dangling label; give the body an outer `{{else}}` fallback for the nothing-collected case.
- **Reuse the shared render.sh helpers** — `badges(.tags)`, `verdict(.validations.X)`,
  `dump(.comments)`, `chain(.previous)` replace the repeated jq (each returns "" when its input is
  absent, so no `{{#if}}` is needed around them).
- **Render tables as HTML, not markdown** — a markdown `| … |` table can drop rows in some
  renderers (marked.js, especially inside chained `.previous` content); a raw HTML `<table>` is
  passed through untouched and always renders every row. Build the body with
  `map("<tr><td>\(cell(.x))</td>…</tr>") | join("\n")`, wrap every cell in `cell(...)` (collapses
  control/whitespace + escapes `& < > |`), and keep a blank line before `<table>` with none inside
  it. `assets/report-template.md` shows the pattern.
- **`skipped` reasons are one sentence** — short and plain, per skipped raw.
- **Logic in readable bash, not jq** — use `jq` for simple **extraction** and final assembly
  (`jq -n --arg …`); do decisions, comparisons, and message-building in plain bash `if`/`else`
  (or SQL for queries). Avoid packing logic into one big jq program — it is hard to read and
  debug. Keep render.sh `{{ }}` expressions to simple field access/formatting, too.

## Skip unsafe snippets — and record it

If a raw snippet **cannot** be made read-only and idempotent, do not force it — **skip it** and
record the decision under the group's `skipped` list in `config.yaml` `status`, so the choice
is durable across re-`ingest`s:

```yaml
status:
  groups:
    crunchy-triage:
      cleaned:
        - { snippet: snippet-cluster-status.sh, from: crunchy-dr-wiki }
      skipped:
        - { raw: crunchy-dr-wiki_reset-replica.sh, reason: "patronictl reinit — not idempotent" }
```

The parser preserves `cleaned` and `skipped` across re-ingests (it only rewrites `sources`).
Mutating operations (`patronictl reinit`/`restart`, `oc edit`/`annotate`, PITR restore,
`pg_dump` writes) are the usual skips; their read-only **observation** counterparts are what
become cleaned blocks.

## Seal the result

After writing the cleaned snippets and recording `cleaned`/`skipped`, seal the source:

```bash
python scripts/parser.py seal --source <name>
```

This stores one SHA in `status` (`seals.<name>`) over the **source doc plus your cleaned
snippets, with the snippets' comments and blank lines stripped**. The doc half is hashed
as-is, so any change to it trips the seal; the snippets are hashed code-only, so editing a
header comment does not, but changing a command does. `check` recomputes it and reports
`SNIPPET CODE DRIFT` when a dev later edits a cleaned command (or the doc moves) — the cue to
run `diff` and propose a doc edit from it (see `BACKPORT.md`), then re-`seal`. Re-run `seal`
whenever you intentionally change a cleaned snippet.

## Hand-authored snippets

A snippet you write by hand (no raw to clean from) joins the system the same way — it just needs
a source to associate with. Use `include`:

```bash
python scripts/parser.py include --source <name> --snippet snippet-foo.sh
```

It records the snippet under that source's `cleaned` and seals in one step. If the snippet has
no source doc, target a **placeholder source** (a spec source with no `url`/`file`); the seal
then covers the snippet alone (edits are still drift-detected, with no back-port target).

## Validators

A **validator** is a separate kind of cleaned snippet that checks the *output* of collection
snippets and reports a verdict, keeping validation logic out of the fetching snippets. Name them
`validator-<kebab>.sh` and start from `assets/validator-template.sh`.

A validator MUST:

- **Read collected JSON on stdin** — the merged collection output, not the cluster/db. A
  validator never fetches; it only inspects what the collection snippets produced.
- **Be graceful** — tolerate partial or missing data: if the data it checks is absent, emit
  `status: "skip"` instead of failing, so a report with only some sections still validates.
- **Be read-only and idempotent** — a pure check over the input; no side effects.
- **Emit a keyed verdict** — `{ check, status, message, docs, sources }`: `check` names the
  report section the verdict sits next to, `status` is `ok|warn|error|skip`, `message` is the OK
  summary or issue string, `docs` is an official-docs link for the concept (see below), and
  `sources` lists the workload/object(s) the data came from (e.g. `["pod/db-0"]`, read from the
  collected JSON) so a reader knows exactly what was inspected.

Implement it **extract-then-branch** (the readable-bash convention above): use `jq` only to pull
the values you check into shell variables, decide `status`/`message` with plain bash `if`/`else`,
and emit with a final `jq -n --arg …`. `assets/validator-template.sh` shows the shape.

Validators are cleaned snippets like any other — recorded in `cleaned` (via `include`) and
sealed. At run time the workflow runs them after the collection snippets, feeds them the merged
JSON, and keys the verdicts under `.validations.<check>`; the report shows each verdict next to
its section. So when cleaning a source, produce the collection `snippet-*` blocks **and** the
`validator-*` checks for the data they emit — fetching and validation stay separate.

**Doc links (the shim).** A validator never hardcodes a URL. It sources its group's shim — a
sibling `snippets/<group>/<group>.sh`, a static `aspect|version -> url` table — and resolves its
link with `doc_url <aspect> <version>` (version `latest` picks the newest on file). The shim is
generated from the registry, so URLs stay out of the snippet and travel with the snippets (no
yq/config at run time). To add or change a link: register the topic in `config.yaml`
`status.docs.topics[]` (aspect, version, group, url), prune dead URLs with `scripts/doc_links.py`
(it follows redirects; only 404/410 are removed), then regenerate with `scripts/doc-link.sh` and
commit the refreshed `snippets/<group>/<group>.sh`. A missing topic (e.g. pruned) makes `doc_url`
warn and the report simply omits the link. Validators also source `utils.sh` for standard
messaging; both libs are optional at run time (the verdict still emits without them).

## Worked example

Raw `working_dir/crunchy-triage/crunchy-notes_get-state-info.sh` (verbatim — hardcoded selector, no
params, mixes output):

```bash
# Fetch main pod name
PRIMARY_POD=$(oc get pods -l postgres-operator.crunchydata.com/role=master -o name | head -n1)
echo "Crunchy Config"
oc exec $PRIMARY_POD -it -- patronictl show-config
echo "Cluster Db Instances State"
oc exec $PRIMARY_POD -it -- patronictl list
```

Cleaned `crunchy-triage/snippet-cluster-status.sh` — parameterized, read-only, idempotent,
JSON out:

```bash
#!/usr/bin/env bash
# snippet-cluster-status — read-only crunchy cluster state as JSON.
# Params: NAMESPACE (env or $1, required). Read-only: patronictl list/show-config only.
set -euo pipefail
NS="${1:-${NAMESPACE:?set NAMESPACE or pass it as arg 1}}"

primary="$(oc get pods -n "$NS" -l postgres-operator.crunchydata.com/role=master \
  -o name 2>/dev/null | head -n1)"
[ -n "$primary" ] || { echo '{"error":"no primary pod found"}'; exit 1; }

members="$(oc exec -n "$NS" "$primary" -- patronictl list -f json 2>/dev/null || echo '[]')"
jq -n --arg ns "$NS" --argjson members "$members" \
  '{namespace: $ns, members: $members}'
```

This is safe to chain: a downstream `snippet-*` reads its JSON on stdin; a final markdown
`snippet-*` renders it for the user (below). The `reinit`/`restart`/PITR raw snippets are
skipped per the rule above.

## Markdown display snippets and render.sh

A terminal display block is a markdown `snippet-*.md` template rendered by
`tools/n8n/render.sh`, which works in and out of n8n:

- `{{ .json.path }}` — filled from JSON on stdin via `jq` (handles arrays/tables).
- `${VAR}` — filled from the environment (scalars). Bare `$FOO` is left untouched.
- `{{#if EXPR }} … [{{else}} …] {{/if}}` — a block kept only when `EXPR` is **present**
  (non-null, non-empty array/object/string). Markers go on their own line and nest; `present`
  is exposed for combining keys: `{{#if (.a|present) or (.b|present) }}`.

**Reports must degrade gracefully.** A report can render more than any one run provides — you
never know which upstream nodes ran, or in what combination. So guard **every** data section
(heading and body together) with `{{#if}}`, and wrap the body in an outer
`{{#if (anything present) }} … {{else}} _nothing collected_ {{/if}}`. A missing key then drops
its section instead of leaving an orphan heading or empty table, and an empty payload (`{}` or
no stdin) yields a clean fallback line — never broken output.

```markdown
<!-- snippet-cluster-report: render via tools/n8n/render.sh -->
# Cluster ${NAMESPACE}

{{#if .members }}
Leader: {{ .members[] | select(.Role=="Leader") | .Member }}

| Member | State | Lag |
|--------|-------|-----|
{{ .members | map("| \(.Member) | \(.State) | \(.["Lag in MB"]) |") | join("\n") }}
{{else}}
_No cluster data collected._
{{/if}}
```

Render it:

```bash
NAMESPACE=f208ae-dev ./snippet-cluster-status.sh f208ae-dev \
  | tools/n8n/render.sh snippet-cluster-report.md
```

In n8n, an Execute-Command node pipes the upstream node's JSON into `render.sh`; the
parameters arrive as args/env. The same files run unchanged from a developer's shell.
