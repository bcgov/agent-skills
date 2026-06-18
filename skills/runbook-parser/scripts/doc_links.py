#!/usr/bin/env python3
"""doc_links.py -- maintain the doc-link registry (config.yaml status.docs.topics) AND the
per-group static shims that validators source. One tool, no yq/bash helper -- it reads the config
directly:

  1. Validate each topic's URL over HTTP, following redirects, and remove the ones whose content
     is gone (HTTP 404/410). Transient failures (timeouts, 5xx, 401/403) are KEPT and reported.
  2. Generate each group's shim -- snippets/<group>/url-shim-<group>.sh (the prefix separator
     matches the group's own) -- from assets/doc-url-shim-template.sh, so a validator resolves a
     doc URL with no yq/config at run time.

    python .../scripts/doc_links.py            # validate + prune dead URLs, then regenerate shims
    python .../scripts/doc_links.py --dry-run  # report only; no config rewrite, no shim writes

Needs internet (the whole point is to confirm the URLs are live). Stdlib only (urllib). Reuses the
parser's config I/O, so the commented spec stays byte-for-byte and only the status block is rewritten.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rb_commands import write_status  # noqa: E402
from rb_config import load_config  # noqa: E402
from rb_log import RunbookError, info, set_quiet, warn  # noqa: E402
from rb_model import Config, write_text_lf  # noqa: E402

GONE = {404, 410}  # only a definitive "gone" prunes a topic; everything else is kept + reported
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config.yaml"
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "doc-url-shim-template.sh"
TOPICS_MARKER = "# @@TOPICS@@"
UA = "Mozilla/5.0 (compatible; runbook-parser doc-link checker)"


def check_url(url: str, timeout: float) -> tuple[bool, str]:
    """Return (gone, detail). gone=True only for a definitive 404/410 (content removed)."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # follows redirects
            return False, f"{resp.status} -> {resp.geturl()}"
    except urllib.error.HTTPError as e:
        if e.code in GONE:
            return True, f"{e.code} {e.reason}"
        return False, f"{e.code} {e.reason} (kept -- not a removal)"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return False, f"unreachable: {e} (kept -- transient)"


def shim_name(group: str) -> str:
    """Shim filename url-shim-<group>.sh; the prefix separator matches the group's own."""
    sep = "_" if "_" in group else "-"
    return f"url{sep}shim{sep}{group}.sh"


def render_shim(template: str, topics: list) -> str:
    """Fill the template's @@TOPICS@@ marker with this group's aspect|version -> url table."""
    rows = [f'  ["{t.get("aspect", "")}|{t.get("version", "")}"]="{t.get("url", "")}"' for t in topics]
    table = "\n".join(rows)
    out: list[str] = []
    for line in template.splitlines():
        if line.strip() == TOPICS_MARKER:
            if table:
                out.append(table)
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def by_group(topics: list) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for t in topics:
        grouped.setdefault((t or {}).get("group", ""), []).append(t)
    return grouped


def generate_shims(cfg: Config, topics: list, dry_run: bool) -> None:
    """Write snippets/<group>/url-shim-<group>.sh for each group present in the registry."""
    template = TEMPLATE.read_text(encoding="utf-8")
    for group, group_topics in by_group(topics).items():
        if not group:
            warn("topic with no group -- skipping its shim")
            continue
        out = cfg.destination / group / shim_name(group)
        content = render_shim(template, group_topics)
        if dry_run:
            info(f"[dry-run] would write {group}/{out.name} ({len(group_topics)} topic(s))")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        write_text_lf(out, content)
        info(f"wrote {group}/{out.name} ({len(group_topics)} topic(s))")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Maintain the doc-link registry + generate the per-group shims.")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="config.yaml path")
    ap.add_argument("--timeout", type=float, default=12.0, help="per-URL timeout (seconds)")
    ap.add_argument("--dry-run", action="store_true", help="report only; no config rewrite, no shim writes")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    set_quiet(args.quiet)

    cfg = load_config(args.config)
    docs = cfg.status.get("docs") or {}
    topics = docs.get("topics") or []
    if not topics:
        info("no topics in status.docs.topics -- nothing to do")
        return 0

    # 1. Validate URLs; collect the gone ones.
    kept: list = []
    removed: list = []
    for t in topics:
        t = t or {}
        url = t.get("url", "")
        label = f"{t.get('aspect', '?')} ({t.get('version', '?')})"
        if not url:
            warn(f"{label}: no url -- removing")
            removed.append(t)
            continue
        gone, detail = check_url(url, args.timeout)
        if gone:
            warn(f"{label}: {detail} -> {url}  [REMOVING]")
            removed.append(t)
        else:
            info(f"{label}: {detail}")
            kept.append(t)

    # 2. Prune dead topics from the registry (unless dry-run).
    if removed and not args.dry_run:
        docs["topics"] = kept
        cfg.status["docs"] = docs
        write_status(cfg, cfg.status, dry_run=False)
        info(f"removed {len(removed)} dead topic(s); {len(kept)} kept")
    elif removed:
        info(f"[dry-run] would remove {len(removed)} dead topic(s); {len(kept)} would remain")
    else:
        info(f"all {len(kept)} topic(s) reachable")

    # 3. Regenerate the per-group shims from the surviving registry.
    generate_shims(cfg, kept, args.dry_run)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RunbookError as e:
        warn(str(e))
        sys.exit(1)
