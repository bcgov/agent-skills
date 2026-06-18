"""Content seal: a comment-insensitive fingerprint of a source's doc + cleaned snippets.

The seal is one SHA-256 over a source's duplicated doc plus every cleaned snippet
derived from it. The cleaned snippets are reduced to code only (comments and blank
lines stripped), so editing a header comment does not trip the seal but changing a
command does. The doc half is hashed as-is, so *any* change to the source doc trips
it too.

Stored in ``status`` at clean time by ``seal``; recomputed by ``check`` -- a mismatch
means a dev changed snippet code (or the doc moved) since the last reconcile, i.e. a
backport candidate.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rb_config import resolve_source
from rb_log import RunbookError
from rb_model import Config, Source, write_text_lf

# Suffix for the verbatim doc copy ``ingest`` parks next to the raws in
# ``working_dir/<group>/``.
DOC_COPY_SUFFIX = ".src.md"


def doc_copy_path(cfg: Config, src: Source) -> Path:
  """Where ``ingest`` parks a source's verbatim doc copy.

  Lives in ``working_dir/<group>/``.
  """
  return cfg.working_dir / src.group / f"{src.docname()}{DOC_COPY_SUFFIX}"


# Subdir under ``working_dir/<group>/`` holding the cleaned snippets as they were at
# seal time, so ``diff`` can show what a dev changed since (the basis for a back-port
# suggestion).
SEALED_SUBDIR = ".sealed"


def sealed_snapshot_path(cfg: Config, group: str, snippet: str) -> Path:
  """Path of a cleaned snippet's seal-time snapshot.

  Lives under ``working_dir/<group>/.sealed/``.
  """
  return cfg.working_dir / group / SEALED_SUBDIR / snippet


def _lf(text: str) -> str:
  """Normalize line endings to LF so the seal never trips on CRLF alone."""
  return text.replace("\r\n", "\n").replace("\r", "\n")


def code_only(text: str, ext: str) -> str:
  """Reduce a snippet to material code.

  Strip comments, blank lines, and trailing whitespace.
  Line-comment languages (sh/yaml/...) drop ``#``-prefixed lines (including the
  shebang); ``sql`` drops ``--``; markdown drops ``<!-- ... -->`` blocks. Dropping
  blanks and trailing whitespace too means formatting-only edits never change the
  result -- only real code does.
  """
  text = _lf(text)
  if ext in ("md", "markdown"):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.split("\n")
  else:
    marker = "--" if ext == "sql" else "#"
    lines = [ln for ln in text.split("\n") if not ln.lstrip().startswith(marker)]
  return "\n".join(ln.rstrip() for ln in lines if ln.strip())


def cleaned_for(cfg: Config, group: str, src_name: str) -> list[dict]:
  """The ``status`` cleaned entries produced from one source (``from == src_name``)."""
  eg = (cfg.status.get("groups") or {}).get(group, {})
  return [c for c in (eg.get("cleaned") or []) if c.get("from") == src_name]


def _read_doc(cfg: Config, src: Source) -> str | None:
  """The duplicated doc text.

  The ``working_dir`` copy if present, else a fresh fetch.
  """
  p = doc_copy_path(cfg, src)
  if p.is_file():
    return p.read_text(encoding="utf-8")
  try:
    return resolve_source(cfg, src)
  except RunbookError:
    return None


def compute_seal(cfg: Config, src: Source) -> str | None:
  """One SHA over the source's doc (as-is) + its cleaned snippets (code only).

  A doc-less source (a placeholder with no ``url``/``file``, holding hand-authored
  snippets) seals over its cleaned snippets alone. Returns ``None`` when there is
  nothing to seal (no cleaned snippets) or an input is missing (a doc source's doc is
  unreachable, or a referenced cleaned snippet is absent on disk).
  """
  cleaned = cleaned_for(cfg, src.group, src.name)
  if not cleaned:
    return None
  h = hashlib.sha256()
  if src.kind() != "none":
    doc = _read_doc(cfg, src)
    if doc is None:
      return None
    h.update(b"doc\x00")
    h.update(_lf(doc).encode("utf-8"))
  for c in sorted(cleaned, key=lambda x: x.get("snippet", "")):
    snip = cfg.destination / src.group / c["snippet"]
    if not snip.is_file():
      return None
    ext = snip.suffix.lstrip(".").lower()
    h.update(b"\x00snip\x00")
    h.update(code_only(snip.read_text(encoding="utf-8"), ext).encode("utf-8"))
  return "sha256:" + h.hexdigest()


def snapshot_cleaned(cfg: Config, src: Source) -> int:
  """Copy ``src``'s cleaned snippets to the ``.sealed`` snapshot dir; return the count.

  Called by ``seal`` so a later ``diff`` can show a dev's change as a unified diff
  against the snapshot. Ephemeral (lives in ``working_dir``); ``diff`` falls back to a
  doc comparison when it is absent (e.g. on a fresh machine).
  """
  n = 0
  for c in cleaned_for(cfg, src.group, src.name):
    snip = cfg.destination / src.group / c["snippet"]
    if not snip.is_file():
      continue
    dest = sealed_snapshot_path(cfg, src.group, c["snippet"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(dest, snip.read_text(encoding="utf-8"))
    n += 1
  return n
