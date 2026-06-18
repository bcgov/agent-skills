"""Domain dataclasses and the text-to-snippets bridge.

:class:`Source`/:class:`Config` mirror the config's ``spec``; :class:`Snippet` is one
raw chunk on disk. :func:`extract_snippets` turns a resolved source document into an
ordered, uniquely-named list of :class:`Snippet`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import rb_markdown


def write_text_lf(path: Path, text: str) -> None:
  """Write *text* with Unix (LF) line endings via bytes, bypassing the platform.

  ``Path.write_text`` rewrites newlines to the OS separator (CRLF on Windows),
  which would corrupt shell snippets and make committed output differ across
  machines. Every parser file write goes through here so snippets and docs are
  deterministically LF.
  """
  data = text.replace("\r\n", "\n").replace("\r", "\n")
  path.write_bytes(data.encode("utf-8"))


@dataclass
class Source:
  """One ``spec.sources[]`` entry.

  ``name`` is a unique id — used to target the source (e.g. for cleaning) and to
  prefix its raw files. ``group`` is the merge bucket: sources sharing a ``group``
  combine into one snippet group. Set exactly one of ``url``/``file``; neither =
  placeholder.
  """

  name: str
  group: str = ""
  description: str = ""
  doc: str | None = None
  url: str | None = None
  file: str | None = None
  index: int = 0

  def kind(self) -> str:
    """Resolution discriminator: ``"file"``, ``"url"`` or ``"none"`` (placeholder)."""
    if self.file:
      return "file"
    if self.url:
      return "url"
    return "none"

  def docname(self) -> str:
    """Filename prefix for this source's raw snippets — its unique ``name``."""
    return rb_markdown.slugify(self.name)


@dataclass
class Snippet:
  """A single raw chunk: its filename, code-fence tag, and source location.

  ``codeblock_tag`` is the original markdown code-fence tag (e.g. ``bash``) for a code
  chunk, kept so reconstruction reproduces the exact opener; it is ``None`` for prose.
  ``line`` is the 1-based source line, which also gives document order within a source.
  """

  file: str
  ext: str
  codeblock_tag: str | None
  section: str | None
  content: str
  source_index: int
  source_ref: str
  line: int

  def is_prose(self) -> bool:
    """True for a prose (``.md``) chunk, as opposed to an extracted code block."""
    return self.ext == "md" and self.codeblock_tag is None


@dataclass
class Config:
  """The loaded config: resolved paths, parsed ``spec`` lists, and raw ``status``."""

  path: Path
  repo_root: Path
  kind: str
  root: Path
  destination: Path
  working_dir: Path
  sources: list[Source]
  status: dict


def extract_snippets(src: Source, body: str) -> list[Snippet]:
  """Decompose ``body`` into raw snippets for ``src``.

  Each chunk becomes a ``<docname>_<section>.<ext>`` file; collisions within the
  source (same section + extension) get a ``-2``/``-3`` suffix. Sections come from
  headings, so a doc with no headings falls back to ``<docname>_intro``
  (header-less docs still work).
  """
  snippets: list[Snippet] = []
  used: set[str] = set()
  docname = src.docname()
  for ch in rb_markdown.decompose(body):
    if ch.kind == "prose":
      ext, tag = "md", None
    else:
      ext, tag = rb_markdown.language_for(ch.info), ch.info
    base = f"{docname}_{rb_markdown.slugify(ch.section or 'intro')}"
    stem, n = base, 1
    while f"{stem}.{ext}" in used:
      n += 1
      stem = f"{base}-{n}"
    used.add(f"{stem}.{ext}")
    snippets.append(
      Snippet(
        file=f"{stem}.{ext}",
        ext=ext,
        codeblock_tag=tag,
        section=ch.section,
        content=ch.text,
        source_index=src.index,
        source_ref=src.file or src.url or src.name,
        line=ch.line,
      )
    )
  return snippets
