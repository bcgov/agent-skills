# config.yaml — schema and model

`config.yaml` is the single manifest for a `RunbookParser`. It is shaped like a Kubernetes
CRD: **`spec:`** is what you write (and is never rewritten, so its comments survive), and
**`status:`** is observed state the parser writes back on `ingest`.

```
kind: RunbookParser          # required, must be exactly this
metadata:
  name: <string>
  labels: { owner: <string> }
spec:                        # human-authored; the parser only reads this
  root: tools/n8n/           # repo-relative base (resolves doc: targets)
  destination: tools/n8n/snippets/   # where cleaned snippet-* live (in <group>/)
  working_dir: /tmp          # where raws + a verbatim doc copy materialize (+ url cache); commit to VC raws
  sources: [ ... ]           # see below
status: { ... }              # machine-owned; written by the parser (do not hand-maintain)
```

## spec.sources[]

| Field         | Type            | Meaning                                                                 |
| ------------- | --------------- | ----------------------------------------------------------------------- |
| `name`        | string          | **Unique** id — targets the source (e.g. for cleaning) and prefixes its raw files. |
| `group`       | string          | Merge bucket: sources sharing a `group` **merge** into one group (defaults to `name`). |
| `description` | string          | What the snippets are — and the **prompt** that guides cleaning (what to produce / skip). |
| `url`         | string \| null  | Wiki/doc/runbook to pull from. Set **exactly one** of `url`/`file`.     |
| `file`        | string \| null  | Repo-relative file to pull from instead of a URL.                       |
| `doc`         | string \| null  | Optional `root`-relative doc the snippets recombine into for drift.     |

- **Merge:** same `group` -> one group (raw under `working_dir/<group>/`, cleaned in `<group>/`),
  but each source still decomposes and round-trips **independently** (its own
  `<name>_<section>` files). Combine domains this way — e.g. a `crunchy-dr-wiki` source and a
  `postgres-triage` source, both `group: crunchy-triage`.
- **Placeholder:** a source with neither `url` nor `file` (`kind: none`) contributes no
  extracted snippets — a slot for hand-authored snippets, added with `include` (they seal over
  the snippets alone, with no back-port target).
- **url normalization:** GitHub `blob` URLs become `raw.githubusercontent.com`; GitHub
  `/wiki/Page` becomes the raw wiki `.md`. Fetches cache into `working_dir`.

## The drift round-trip (`src -> snippets -> src`, per source)

Each source decomposes losslessly, so recombining *that source's* snippets reproduces *its*
document byte-for-byte — independently, even when several sources share a group. Two sources
in a group give two independent round-trips. There is no whole-group reassembly; composing the cleaned blocks into runnable
workflows is n8n's job. Drift detection compares a source's reconstruction against its doc
target:

- If `doc:` is set, the target is `root/doc`. If not, the target is the source itself
  (`src == doc`).
- `ingest` records each source's drift state in `status` (`in_sync` / `drifted` /
  `doc_missing`). `check` re-computes it and exits **2** on drift. (Back-porting a cleaned fix
  is separate: the seal detects it and `diff` shows it — see `BACKPORT.md`.)
- Comparison is whitespace-lenient (trailing whitespace and the final newline are
  ignored), so cosmetic edits do not register as drift.

## status (written by the parser)

The committed `status` tracks **cleaned** work, not every raw — per group: `sources`
(parser-written: drift, etc.) plus the agent-maintained **`cleaned`**, **`skipped`**, and
**`seals`** entries. The parser preserves `cleaned`/`skipped`/`seals` across ingests and only
rewrites `sources`. (The raw inventory reconstruction needs lives in
`working_dir/<group>/index.yaml`, not here.)

```yaml
status:
  groups:
    crunchy-triage:
      sources:                          # parser-written
        - name: crunchy-dr-wiki
          ref: https://…/wiki/Disaster-Recovery
          kind: url
          doc: crunchy-disaster-recovery.md
          drift: doc_missing
      cleaned:                          # agent: the blocks you produced
        - { snippet: snippet-cluster-status.sh, from: crunchy-dr-wiki }
      skipped:                          # agent: raws intentionally left (with a reason)
        - { raw: crunchy-dr-wiki_4-perform-pitr.sh, reason: "not idempotent — PITR" }
      seals:                            # `seal`: sha(doc + cleaned code, comments excluded), per source
        crunchy-dr-wiki: sha256:d846e79f…
```

`seals` is the **snippet-code drift** baseline: `seal` writes it after cleaning, `check`
recomputes it. It is distinct from `sources[].drift` above — that compares a *doc* to its
reconstruction; the seal compares the *cleaned snippets'* code (comments excluded) to when
they were last reconciled. See `CLEANING.md` and `BACKPORT.md`.

## Comment safety

The parser rewrites only from a top-level `status:` marker to end-of-file; everything above
(your commented `spec`) is left byte-for-byte — `spec` stays human-owned, `status` stays
machine-owned. The `spec` is parsed with PyYAML, so any valid YAML is fine.
