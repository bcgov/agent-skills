"""The subcommands and their helpers (the orchestration layer).

* :func:`cmd_ingest` — sources -> raw snippets (+ doc copy) + ``status``.
* :func:`cmd_check`  — drift detection: round-trip + seal recheck (read-only; exit 2 on drift).
* :func:`cmd_seal`   — record the per-source content seal + snapshot the cleaned snippets.
* :func:`cmd_diff`   — show how cleaned snippets diverged from their seal (read-only back-port aid).

Status write-back replaces only the machine-owned ``status:`` block (from its marker to
end-of-file), leaving the commented ``spec`` untouched, and preserves agent-set ``cleaned``
annotations across ingests.
"""

from __future__ import annotations

import difflib
import re
import sys
from typing import Any, Optional

import yaml

from rb_config import resolve_source
from rb_log import RunbookError, info, warn
from rb_model import Config, Snippet, Source, extract_snippets, write_text_lf
from rb_reconstruct import (
    drift_state,
    load_doc_target,
    load_raw_index,
    normalize,
    render_from_disk,
    render_from_snippets,
)
from rb_seal import (
    DOC_COPY_SUFFIX,
    cleaned_for,
    compute_seal,
    doc_copy_path,
    sealed_snapshot_path,
    snapshot_cleaned,
)


# --------------------------------------------------------------------------------------
# Selection helpers
# --------------------------------------------------------------------------------------


def select_sources(cfg: Config, groups: list[str], sources: list[str]) -> list[Source]:
    """Sources to act on, narrowed by ``--group`` (exact group) and ``--source`` (exact unique
    source name). Both filters apply together (AND)."""
    out = []
    for s in cfg.sources:
        if groups and s.group not in groups:
            continue
        if sources and s.name not in sources:
            continue
        out.append(s)
    return out


def group_order(cfg: Config) -> list[str]:
    """Group names in first-seen config order (sources sharing a group merge into one)."""
    seen: list[str] = []
    for s in cfg.sources:
        if s.group not in seen:
            seen.append(s.group)
    return seen


def source_metas(cfg: Config, src: Source) -> list[dict]:
    """The raw-index entries (from ``working_dir/<group>/index.yaml``) belonging to one source."""
    ref = src.file or src.url
    return [m for m in load_raw_index(cfg, src.group) if m.get("from") == ref]


# --------------------------------------------------------------------------------------
# ingest
# --------------------------------------------------------------------------------------


def cmd_ingest(cfg: Config, args) -> int:
    """Resolve sources, extract raws into ``working_dir``, and rewrite the committed ``status``.

    Raws (and their index sidecar) go under ``working_dir/<group>/`` — ephemeral unless
    ``working_dir`` is a committed path. With ``--group``/``--source`` this is a *partial*
    ingest: only the selected sources are fetched and written; pruning, the index, and the
    ``sources`` status are scoped to them (other sources are left intact).
    """
    selected = select_sources(cfg, args.group or [], args.source or [])
    partial = bool(args.group) or bool(args.source)
    groups: dict[str, list[Snippet]] = {g: [] for g in group_order(cfg)}
    source_status: dict[str, list[dict]] = {g: [] for g in group_order(cfg)}
    processed_refs: set[str] = set()
    processed_docnames: dict[str, set[str]] = {}

    failures = 0
    for src in selected:
        try:
            body = resolve_source(cfg, src)
        except RunbookError as e:
            warn(f"  failed: source '{src.name}': {e}")
            failures += 1
            continue
        processed_refs.add(src.file or src.url or src.name)
        if body is None:
            info(f"  note: source '{src.name}' has no url/file — skipping (placeholder)")
            source_status[src.group].append({"name": src.name, "ref": src.name, "kind": "none", "drift": "n/a"})
            continue
        snippets = extract_snippets(src, body)
        groups[src.group].extend(snippets)
        write_doc_copy(cfg, src, body, args.dry_run)
        processed_docnames.setdefault(src.group, set()).add(src.docname())
        source_status[src.group].append(
            {
                "name": src.name,
                "ref": src.file or src.url,
                "kind": src.kind(),
                "doc": src.doc,
                "drift": drift_state(cfg, src, snippets),
            }
        )
        info(f"  parsed: {src.name} <- {src.file or src.url} ({len(snippets)} snippet(s))")

    for gname in group_order(cfg):
        if partial and gname not in processed_docnames:
            continue
        write_group(cfg, gname, groups[gname], args.dry_run, processed_docnames.get(gname) if partial else None)

    status = build_status(cfg, source_status, processed_refs if partial else None)
    write_status(cfg, status, args.dry_run)

    if failures:
        warn(f"completed with {failures} source failure(s)")
        return 1
    return 0


def write_group(cfg: Config, group: str, snippets: list[Snippet], dry_run: bool, prune_docnames: Optional[set] = None) -> None:
    """Write a group's raw files + index sidecar under ``working_dir/<group>/`` and prune stale ones.

    ``prune_docnames`` (partial ingests) scopes pruning to files whose source was processed
    this run — files from the ``<docname>_`` prefix of any other source are left alone.
    """
    group_dir = cfg.working_dir / group
    planned = {s.file: s.content + "\n" for s in snippets}
    if group_dir.is_dir():
        for existing in sorted(group_dir.glob("*")):
            if not existing.is_file() or existing.name == "index.yaml" or "_" not in existing.stem:
                continue  # skip the index, directories, and non-raw files
            if prune_docnames is not None and existing.stem.split("_", 1)[0] not in prune_docnames:
                continue  # source not processed this run — leave its files alone
            if existing.name not in planned:
                if dry_run:
                    info(f"  [dry-run] would prune {group}/{existing.name}")
                else:
                    existing.unlink()
                    info(f"  pruned: {group}/{existing.name}")
    for fname, content in planned.items():
        path = group_dir / fname
        lf = content.replace("\r\n", "\n").replace("\r", "\n")
        if path.is_file() and path.read_bytes() == lf.encode("utf-8"):
            continue
        if dry_run:
            info(f"  [dry-run] would write {group}/{fname}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_lf(path, content)
        info(f"  wrote: {group}/{fname}")
    _write_raw_index(cfg, group, snippets, prune_docnames, dry_run)


def write_doc_copy(cfg: Config, src: Source, body: str, dry_run: bool) -> None:
    """Save a verbatim copy of the source doc to ``working_dir/<group>/<docname>.src.md``.

    This duplicated doc is one half of the source's content seal (the other half is its
    cleaned snippets). Ephemeral like the raws, and refetched on demand if absent.
    """
    path = cfg.working_dir / src.group / f"{src.docname()}{DOC_COPY_SUFFIX}"
    if dry_run:
        info(f"  [dry-run] would copy doc {src.group}/{path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(path, body)
    info(f"  copied doc: {src.group}/{path.name}")


def _write_raw_index(cfg: Config, group: str, snippets: list[Snippet], prune_docnames: Optional[set], dry_run: bool) -> None:
    """Write the raw-index sidecar (``working_dir/<group>/index.yaml``) that reconstruction reads.

    Partial ingests merge: index entries for sources not processed this run are kept.
    """
    fresh = [
        {"file": s.file, "section": s.section, "codeblock_tag": s.codeblock_tag, "from": s.source_ref, "line": s.line}
        for s in sorted(snippets, key=lambda x: (x.source_index, x.line))
    ]
    if prune_docnames is not None:
        kept = [m for m in load_raw_index(cfg, group) if m.get("file", "").split("_", 1)[0] not in prune_docnames]
        entries = sorted(kept + fresh, key=lambda m: (m.get("from", ""), m.get("line", 0)))
    else:
        entries = fresh
    if dry_run:
        info(f"  [dry-run] would write {group}/index.yaml ({len(entries)} raws)")
        return
    path = cfg.working_dir / group / "index.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(
        path,
        yaml.safe_dump(entries, default_flow_style=False, sort_keys=False, width=10000, allow_unicode=True),
    )


# --------------------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------------------


def build_status(cfg: Config, source_status, processed_refs=None) -> dict:
    """Assemble the committed ``status``: per group, parser-written ``sources`` plus the
    agent-maintained ``cleaned``/``skipped`` lists, preserved across ingests.

    With ``processed_refs`` (partial ingest), ``sources`` entries for sources not processed
    this run are kept; ``cleaned``/``skipped`` are always preserved whole.
    """
    existing = cfg.status.get("groups") or {}
    out_groups: dict[str, Any] = {}
    for gname in group_order(cfg):
        eg = existing.get(gname, {})
        fresh_sources = source_status.get(gname, [])
        if processed_refs is not None:
            kept = [s for s in (eg.get("sources") or []) if s.get("ref") not in processed_refs]
            sources = kept + fresh_sources
        else:
            sources = fresh_sources
        entry: dict[str, Any] = {"sources": sources}
        if eg.get("cleaned"):
            entry["cleaned"] = eg["cleaned"]
        if eg.get("skipped"):
            entry["skipped"] = eg["skipped"]
        if eg.get("seals"):
            entry["seals"] = eg["seals"]
        out_groups[gname] = entry
    result: dict[str, Any] = {"groups": out_groups}
    # Preserve the doc-link registry (status.docs); it is maintained by doc_links.py /
    # doc-link.sh, not by ingest, so carry it across reconciles untouched (like seals).
    docs = cfg.status.get("docs")
    if docs:
        result["docs"] = docs
    return result


def write_status(cfg: Config, status: dict, dry_run: bool) -> None:
    """Replace the config's ``status:`` block (marker to EOF), leaving ``spec`` byte-for-byte.

    Only the machine-owned ``status:`` block is re-emitted; the commented ``spec`` above the
    marker is preserved exactly, since PyYAML's load/dump would otherwise drop its comments.
    """
    lines = cfg.path.read_text(encoding="utf-8").split("\n")
    cut = next((i for i, ln in enumerate(lines) if re.match(r"^status\s*:", ln)), None)
    spec_part = "\n".join(lines[:cut]) if cut is not None else "\n".join(lines).rstrip("\n")
    if not spec_part.endswith("\n"):
        spec_part += "\n"
    block = yaml.safe_dump(
        {"status": status}, default_flow_style=False, sort_keys=False, width=10000, allow_unicode=True
    )
    if dry_run:
        info(f"  [dry-run] would rewrite status block ({len(status.get('groups', {}))} group(s))")
        return
    write_text_lf(cfg.path, spec_part + block)
    info("  wrote status block to config.yaml (spec untouched)")


# --------------------------------------------------------------------------------------
# seal
# --------------------------------------------------------------------------------------


def cmd_seal(cfg: Config, args) -> int:
    """Record each selected source's content seal (sha of doc + cleaned code) in ``status``.

    Run after cleaning a source. The seal is preserved across ingests; ``check`` recomputes it
    and flags a mismatch as snippet-code drift -- a dev changed a cleaned command (or the doc
    moved), and the change may need backporting to the source doc.
    """
    status = cfg.status if cfg.status.get("groups") else {"groups": {}}
    sealed = 0
    for src in select_sources(cfg, args.group or [], args.source or []):
        digest = compute_seal(cfg, src)
        if digest is None:
            warn(f"  {src.name}: nothing to seal (no cleaned snippets, or doc/snippet missing)")
            continue
        grp = status["groups"].setdefault(src.group, {})
        grp.setdefault("seals", {})[src.name] = digest
        if not args.dry_run:
            snapshot_cleaned(cfg, src)
        info(f"  sealed: {src.name} -> {digest[:23]}...")
        sealed += 1
    if not sealed:
        return 0
    if args.dry_run:
        info("  [dry-run] would write seals to status")
        return 0
    write_status(cfg, status, args.dry_run)
    return 0


# --------------------------------------------------------------------------------------
# include
# --------------------------------------------------------------------------------------


def cmd_include(cfg: Config, args) -> int:
    """Associate hand-written cleaned snippet(s) with a source, then seal -- in one step.

    The shortcut for a snippet you authored by hand (not produced from a raw): it records the
    snippet under the source's ``cleaned`` list in ``status`` and seals. For a snippet with no
    source doc, target a placeholder source (one with no ``url``/``file``) -- the seal then
    covers the snippet alone.
    """
    sources = select_sources(cfg, args.group or [], args.source or [])
    if len(sources) != 1:
        raise RunbookError("include needs exactly one --source (the source to associate with)")
    src = sources[0]
    files = args.snippet or []
    if not files:
        raise RunbookError("include needs at least one --snippet FILE")
    missing = [f for f in files if not (cfg.destination / src.group / f).is_file()]
    if missing:
        where = cfg.destination / src.group
        raise RunbookError(f"snippet(s) not found under {where}: {', '.join(missing)} (write them first)")

    if not cfg.status.get("groups"):
        cfg.status = {"groups": {}}
    cleaned = cfg.status["groups"].setdefault(src.group, {}).setdefault("cleaned", [])
    have = {c.get("snippet") for c in cleaned}
    for f in files:
        if f in have:
            info(f"  already included: {f}")
        else:
            cleaned.append({"snippet": f, "from": src.name})
            info(f"  included: {f} (from {src.name})")
    return cmd_seal(cfg, args)


# --------------------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------------------


def cmd_check(cfg: Config, args) -> int:
    """Compare each source's reconstruction to its doc; print a diff and exit 2 on drift."""
    drift = 0
    for src in select_sources(cfg, args.group or [], args.source or []):
        if src.kind() == "none":
            continue
        metas = source_metas(cfg, src)
        if metas:
            generated = render_from_disk(cfg, src.group, metas)
        else:
            try:
                body = resolve_source(cfg, src)
            except RunbookError as e:
                warn(f"  {src.name}: {e}")
                drift = max(drift, 1)
                continue
            if body is None:
                continue
            generated = render_from_snippets(extract_snippets(src, body))
        target = load_doc_target(cfg, src)
        if target is None:
            print(f"  {src.name}: no local doc mirror ({src.doc}) — seal covers doc drift")
            continue
        if normalize(generated) == normalize(target):
            print(f"  {src.name}: in_sync")
        else:
            print(f"  {src.name}: DRIFTED")
            sys.stdout.writelines(
                difflib.unified_diff(
                    normalize(target).splitlines(keepends=True),
                    normalize(generated).splitlines(keepends=True),
                    fromfile=f"{src.name} (doc)",
                    tofile=f"{src.name} (from snippets)",
                )
            )
            drift = max(drift, 2)
    return max(drift, _check_seals(cfg, args))


def _check_seals(cfg: Config, args) -> int:
    """Recompute each selected source's seal; report snippet-code drift (a backport candidate)."""
    groups = cfg.status.get("groups") or {}
    worst = 0
    for src in select_sources(cfg, args.group or [], args.source or []):
        stored = (groups.get(src.group, {}).get("seals") or {}).get(src.name)
        if not stored:
            continue
        current = compute_seal(cfg, src)
        if current is None:
            print(f"  {src.name}: seal n/a (doc or a cleaned snippet missing)")
        elif current != stored:
            print(f"  {src.name}: SNIPPET CODE DRIFT - doc/cleaned changed since seal; review backport")
            worst = max(worst, 2)
        else:
            print(f"  {src.name}: sealed in_sync")
    return worst


# --------------------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------------------


def cmd_diff(cfg: Config, args) -> int:
    """Show how a source's cleaned snippets diverged from their seal, to drive a doc back-port.

    Read-only. For each selected source whose seal no longer matches, prints each cleaned
    snippet's change as a unified diff against the seal-time snapshot (the dev's edit) and points
    at the source doc, so the agent can propose the doc edits that carry the substantive change
    back. Falls back to naming the files when no snapshot is present. Exit 2 if any source
    diverged (like ``check``), 0 otherwise.
    """
    groups = cfg.status.get("groups") or {}
    diverged = 0
    for src in select_sources(cfg, args.group or [], args.source or []):
        stored = (groups.get(src.group, {}).get("seals") or {}).get(src.name)
        if not stored:
            continue
        if compute_seal(cfg, src) == stored:
            print(f"  {src.name}: sealed in_sync")
            continue
        diverged = 2
        docp = doc_copy_path(cfg, src)
        has_doc = src.kind() != "none" and docp.is_file()
        if has_doc:
            print(f"  {src.name}: SEAL BROKEN - cleaned diverged; propose a doc back-port")
            print(f"    source doc: {docp}")
        else:
            print(f"  {src.name}: SEAL BROKEN - hand-authored snippet changed (no source doc)")
        for c in cleaned_for(cfg, src.group, src.name):
            snip = cfg.destination / src.group / c["snippet"]
            snap = sealed_snapshot_path(cfg, src.group, c["snippet"])
            current = snip.read_text(encoding="utf-8") if snip.is_file() else ""
            if not snap.is_file():
                print(f"    {c['snippet']}: no seal snapshot here - compare it against the doc by hand")
                continue
            lines = list(
                difflib.unified_diff(
                    snap.read_text(encoding="utf-8").splitlines(keepends=True),
                    current.splitlines(keepends=True),
                    fromfile=f"{c['snippet']} (sealed)",
                    tofile=f"{c['snippet']} (current)",
                )
            )
            if lines:
                sys.stdout.writelines(lines)
        if has_doc:
            print(
                "    -> update the source doc to carry the substantive change back; ignore "
                "cleaned-only params/guards/jq, then re-seal."
            )
        else:
            print("    -> review the change above; re-seal (seal/include) once it is intended.")
    return diverged
