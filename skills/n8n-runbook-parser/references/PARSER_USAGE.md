# parser.py — CLI reference

Python 3.9+ with PyYAML and markdown-it-py (`pip install pyyaml markdown-it-py`). Runs
locally or in CI (not inside the n8n container). Run from the repo root.

```
python tools/n8n/skills/runbook-parser/scripts/parser.py <command> [options]
```

## Commands

| Command            | Does                                                                       | Exit codes                  |
| ------------------ | -------------------------------------------------------------------------- | --------------------------- |
| `ingest` (default)  | resolve sources -> extract raws (+ a verbatim doc copy) -> write files -> write `status` | 0 ok / 1 a source failed |
| `check`            | recombine and diff vs source/doc, **and** recompute seals; **read-only**   | 0 in-sync / 2 drift / 1 err |
| `diff`             | show how cleaned snippets diverged from their seal (read-only back-port aid) | 0 in_sync / 2 diverged |
| `seal`             | record sha(doc + cleaned code, comments excluded) into `status` (after cleaning) | 0 / 1               |
| `include`          | associate hand-written snippet(s) (`--source X --snippet f.sh`) with a source, then seal | 0 / 1   |

`check` returns a distinct **2** for drift (vs **1** for a tool error) so CI can tell
"docs and code diverged" from "the run failed" — like `git diff --exit-code`.

## Options (all commands)

| Option            | Effect                                                                 |
| ----------------- | --------------------------------------------------------------------- |
| `--config PATH`   | config path (default `tools/n8n/config.yaml`)                         |
| `--group NAME`    | limit to sources in this group (exact name); repeatable             |
| `--source NAME`   | limit to the source with this exact unique `name`; repeatable      |
| `--snippet FILE`  | cleaned snippet to associate with `--source` (for `include`; repeatable) |
| `--dry-run`       | print intended writes/diffs without touching disk                    |
| `-q, --quiet`     | suppress progress output                                             |
| `-h, --help`      | argparse help                                                        |

## Partial ingests (`--group` / `--source`)

Selecting a subset of sources makes `ingest` **partial** and non-destructive: only the chosen
sources are fetched and written, and pruning and `status` are scoped to them (other sources'
files and status entries are left intact). `--group NAME` picks a whole group by name;
`--source NAME` picks the source with that exact unique `name` — the way to iterate on one
source when several share a `group`. Example — regenerate just the wiki:

```bash
python tools/n8n/skills/runbook-parser/scripts/parser.py ingest --source crunchy-dr-wiki
```

## Cache

- `url:` sources are fetched and cached under `working_dir`
  (`runbook-parser-<hash>-<slug>.cache`). Override the location with the
  `RUNBOOK_PARSER_CACHE` environment variable (handy when `/tmp` is awkward locally).
- On a fetch failure the parser falls back to the cached copy with a warning (resilience if
  upstream is briefly down).

## URL normalization

- `https://github.com/OWNER/REPO/blob/REF/path` -> `https://raw.githubusercontent.com/OWNER/REPO/REF/path`
- `https://github.com/OWNER/REPO/wiki/Page` -> `https://raw.githubusercontent.com/wiki/OWNER/REPO/Page.md`
- anything else is fetched as-is.

## Snippet layout

```
working_dir/<group>/         # raws — ephemeral (or version-controlled if working_dir is committed)
  <name>.src.md              #   verbatim copy of the source doc (one half of the seal)
  <name>_<section>.md        #   raw prose chunk (parser-written)
  <name>_<section>.sh        #   raw code chunk (also .yaml/.sql/.json/.txt)
  index.yaml                 #   raw inventory that reconstruction reads
  .sealed/<snippet>          #   cleaned snippets as of the last `seal` (diff compares to these)

snippets/<group>/            # cleaned — committed
  snippet-<section>.sh       #   cleaned block (the agent writes these)
```

Raw names: `_` separates structural parts, `-` is kebab within a part. Multiple chunks in one
section get a `-2`, `-3` suffix. Reconstruction orders by source `line` (from `index.yaml`), not
filename sort. A doc with no headings falls back to `<name>_intro`.

## Seal (snippet-code drift)

`seal` records one SHA per source in `status.groups.<group>.seals.<name>`, over the source's
duplicated doc (hashed as-is) plus its cleaned snippets (comments and blank lines stripped).
Run it after cleaning. `check` recomputes every stored seal and prints `SNIPPET CODE DRIFT`
(exit 2) when a cleaned command — or the source doc — changed since the seal, while a
comment-only edit is ignored. `seal` also snapshots the cleaned snippets to
`working_dir/<group>/.sealed/`, so `diff` can show a later edit as a unified diff. On a machine
without the `working_dir` doc copy the seal refetches the source. Seals are preserved across
`ingest`s (like `cleaned`/`skipped`).

A **doc-less source** (a placeholder with no `url`/`file`) seals over its cleaned snippets
alone — how hand-authored snippets get drift detection without a source doc. `include`
(`--source X --snippet f.sh`) adds a hand-written snippet to a source's `cleaned` and seals it
in one step; for one with no doc, target a placeholder source. `diff` on a doc-less source
shows the snippet change without a back-port target.

## No-network smoke test

Point a scratch config at a local file and exercise the whole loop without the network:

```bash
cat > /tmp/scratch.yaml <<'YAML'
kind: RunbookParser
metadata: { name: scratch }
spec:
  root: tools/n8n/
  destination: tools/n8n/_scratch_snippets/
  working_dir: /tmp
  sources:
    - { name: crunchy-triage, description: scratch, file: crunchy-notes.md }
YAML
P="python tools/n8n/skills/runbook-parser/scripts/parser.py --config /tmp/scratch.yaml"
$P ingest            # writes snippets + status
$P ingest            # idempotent: no further writes
$P check            # in_sync (exit 0) — reconstruction matches the source

# back-port drift demo (needs a cleaned snippet recorded under status.cleaned):
$P seal             # snapshot the cleaned snippet(s) + record the seal
# edit a cleaned command, then:
$P check            # -> SNIPPET CODE DRIFT (exit 2)
$P diff             # -> unified diff of the change + the doc path to back-port into
```

Notes:
- `ingest` is idempotent — a second run changes nothing on disk.
- `check` exits 0 only when the snippets reconstruct the source and every seal matches.
- `diff` is read-only — it shows a back-port; it never writes the doc.
