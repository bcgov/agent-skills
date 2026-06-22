# Backporting a cleaned fix (the `diff` flow)

Developers edit **cleaned** `snippet-*` blocks, never the raw snippets. When they fix a command
there, the fix should flow back to the source document so the runbook stays canonical. There is
**no mechanical reverse**: `raw -> cleaned` is a lossy, judgement-based rewrite (parameterized,
guarded, `jq`-shaped), so cleaned cannot be auto-recombined into the doc. Instead the **seal**
detects the divergence and the **agent proposes** the doc edit, with `diff` showing exactly what
changed.

## The flow

```
dev edits a snippet-* (fixes a command)
   |  parser.py check    ->  SNIPPET CODE DRIFT (the seal no longer matches)
   v
parser.py diff --source <name>
   |  prints a unified diff of each cleaned snippet vs its seal-time snapshot (the dev's edit),
   |  and the path to the source doc copy.
   v
agent proposes the doc edit  (read the diff + the doc; carry the substantive change back -- a
   corrected selector, flag, path, command. Ignore cleaned-only scaffolding: param parsing,
   set -euo pipefail, jq shaping -- that is not in the doc.)
   v
apply to the source doc / wiki  (for a url source, paste into the wiki by hand)
   v
parser.py ingest   (re-derive raws from the updated source)
parser.py seal    (re-seal: snapshot + hash are reconciled again)
```

This mirrors cleaning, in reverse: cleaning is doc -> cleaned by judgement; back-porting is a
cleaned-fix -> doc by judgement. The tooling only **detects** (`check`/seal) and **shows**
(`diff`) -- it never writes the doc.

## What `diff` shows

`diff` is read-only. For each selected source whose seal has broken it prints:

- a **unified diff** of each cleaned snippet against its **seal-time snapshot**
  (`working_dir/<group>/.sealed/<snippet>`) -- i.e. exactly what the dev changed; and
- the path to the **source doc copy** (`working_dir/<group>/<name>.src.md`) to back-port into.

The snapshot is written by `seal` and lives in `working_dir`, so `diff` shows a precise change
on the machine where the edit was made. On a machine without the snapshot it names the files to
compare by hand instead. `diff` exits **2** when any source diverged, **0** otherwise.

## Targets

- **`file:` source** -- the doc is a local file; apply the proposed edit there, then `ingest`
  re-reads it.
- **`url:` source** -- a remote wiki cannot be pushed to; paste the proposed edit into the wiki
  by hand, then the next `ingest` refetches it. (An optional `doc:` keeps a committed local
  mirror for reference.)

## Guardrails

- Never edit the doc *and* the cleaned snippet separately and call it done -- back-port through
  the seal so they converge, then re-`seal`.
- A cleaned fix that only touches cleaned-only plumbing (param handling, output shaping) has
  nothing to back-port -- the doc documents the *operation*, not the scaffolding.
- Run `check` (or `diff`) after a back-port; the source should be `sealed in_sync` again.
