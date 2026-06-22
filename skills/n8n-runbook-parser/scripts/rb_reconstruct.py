"""Snippet -> document reconstruction, and the drift comparison built on it.

Because :func:`~rb_markdown.decompose` is lossless, concatenating a source's raw
snippets in order reproduces the document. :func:`render_from_disk` does that from
the raw files in ``working_dir/<group>/`` (what ``check`` compares against), ordered
by the sidecar index; :func:`render_from_snippets` does it from in-memory snippets
(used during ``ingest``).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from rb_model import Config, Snippet, Source


def _eol(text: str) -> str:
  """Normalize line endings (CRLF -> LF).

  Used by :func:`normalize` for tolerant comparisons.
  """
  return text.replace("\r\n", "\n")


def normalize(text: str) -> str:
  """Lenient normalization for drift checks.

  Strips trailing whitespace and the final newline. Keeps cosmetic edits (trailing
  spaces, a missing final newline) from registering as drift.
  """
  body = "\n".join(line.rstrip() for line in _eol(text).split("\n"))
  return body.strip("\n") + "\n"


def _read_snippet_content(path: Path) -> str:
  """Read a snippet file, stripping the single trailing newline the writer added."""
  c = path.read_text(encoding="utf-8")
  return c[:-1] if c.endswith("\n") else c


def render_from_snippets(snippets: list[Snippet]) -> str:
  """Reconstruct a document from in-memory snippets (prose verbatim, code re-fenced)."""
  parts: list[str] = []
  for s in sorted(snippets, key=lambda x: x.line):
    if s.is_prose():
      parts.append(s.content)
    else:
      parts.append(f"```{s.codeblock_tag or ''}\n{s.content}\n```")
  return "\n".join(parts)


def load_raw_index(cfg: Config, group: str) -> list[dict]:
  """Read the raw-snippet index sidecar.

  Reads ``working_dir/<group>/index.yaml``; returns ``[]`` if absent.
  """
  path = cfg.working_dir / group / "index.yaml"
  if not path.is_file():
    return []
  return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def render_from_disk(cfg: Config, group: str, metas: list[dict]) -> str:
  """Reconstruct a document from the raw files in ``working_dir/<group>/``.

  Ordered by ``line``. ``metas`` are the raw-index entries for one source
  (file/line/codeblock_tag), from the sidecar index written alongside the raws.
  """
  parts: list[str] = []
  group_dir = cfg.working_dir / group
  for s in sorted(metas, key=lambda x: x.get("line", 0)):
    content = _read_snippet_content(group_dir / s["file"])
    if s.get("codeblock_tag") is None and s["file"].endswith(".md"):
      parts.append(content)
    else:
      parts.append(f"```{s.get('codeblock_tag') or ''}\n{content}\n```")
  return "\n".join(parts)


def load_doc_target(cfg: Config, src: Source) -> str | None:
  """The text a source is compared against: its ``doc`` file, else the source itself."""
  if src.doc:
    p = cfg.root / src.doc
    return p.read_text(encoding="utf-8") if p.is_file() else None
  if src.kind() == "file":
    p = cfg.repo_root / src.file
    return p.read_text(encoding="utf-8") if p.is_file() else None
  return None


def drift_state(cfg: Config, src: Source, snippets: list[Snippet]) -> str:
  """Classify a source as ``in_sync`` / ``drifted`` / ``doc_missing`` / ``n/a``."""
  target = load_doc_target(cfg, src)
  if target is None:
    return "doc_missing" if src.doc else "n/a"
  generated = render_from_snippets(snippets)
  return "in_sync" if normalize(generated) == normalize(target) else "drifted"
