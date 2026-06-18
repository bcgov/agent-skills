"""Markdown decomposition (via markdown-it-py) and the slug/language helpers.

:func:`decompose` is the heart of the parser: it splits a document into an ordered list of
:class:`Chunk` objects (prose runs and fenced code blocks). It uses markdown-it-py to locate
fenced code blocks and headings (handling CommonMark edge cases — tilde fences, info
strings, ATX/setext headings — that a regex scanner gets wrong), then slices the *original*
lines so the split stays lossless: recombining the chunks reproduces the document byte for
byte, which is what powers drift detection.

Only fenced code becomes a code chunk; indented (4-space) code blocks are left as prose, so
they round-trip verbatim without re-indentation guesswork.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from markdown_it import MarkdownIt

_MD = MarkdownIt("commonmark")

# Fence info string -> file extension / "language". Anything unmapped keeps its own token
# (so a ```rust block becomes .rust); blank/info-less code blocks become .txt.
_LANG = {
    "bash": "sh", "sh": "sh", "shell": "sh", "zsh": "sh", "console": "sh",
    "yaml": "yaml", "yml": "yaml", "json": "json", "sql": "sql",
    "python": "py", "py": "py", "text": "txt", "": "txt",
}


def slugify(text: str) -> str:
    """Lowercase, collapse non-alphanumerics to ``-`` and trim — mirrors pull.sh's slugify."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "snippet"


def language_for(info: Optional[str]) -> str:
    """Map a fence info string (e.g. ``bash``) to a snippet language/extension (``sh``)."""
    tok = (info or "").strip().split(" ")[0].split(",")[0].lower() if info else ""
    return _LANG.get(tok, tok or "txt")


@dataclass
class Chunk:
    """One ordered piece of a decomposed document.

    ``kind`` is ``"prose"`` or ``"code"``; ``info`` is the original fence info string for
    code chunks (kept so the round-trip reproduces ```` ```bash ```` exactly); ``line`` is
    the 1-based source line where the chunk begins.
    """

    kind: str
    section: Optional[str]
    text: str
    info: Optional[str]
    line: int


def decompose(text: str) -> list[Chunk]:
    """Split a markdown document into ordered prose/code chunks.

    Fenced blocks and heading positions come from markdown-it-py's token line-maps; the chunk
    text is sliced from the original lines so nothing is normalised. Prose is broken at
    headings (so each chunk maps to a section), but a whitespace-only run before a heading is
    merged into it, so blank-line separators do not become empty files.
    """
    lines = text.split("\n")
    tokens = _MD.parse(text)
    # fence open line (0-based) -> (end line exclusive, info string, fence markup)
    fences = {t.map[0]: (t.map[1], t.info.strip(), t.markup) for t in tokens if t.type == "fence" and t.map}
    # heading start line (0-based) -> heading text (the inline token follows heading_open)
    headings = {
        t.map[0]: tokens[i + 1].content.strip()
        for i, t in enumerate(tokens)
        if t.type == "heading_open" and t.map
    }

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_line = 1
    section: Optional[str] = None

    def flush() -> None:
        nonlocal buf
        if buf:
            chunks.append(Chunk("prose", section, "\n".join(buf), None, buf_line))
        buf = []

    i = 0
    while i < len(lines):
        if i in fences:
            flush()
            end, info, markup = fences[i]
            closed = end - 1 < len(lines) and lines[end - 1].lstrip().startswith(markup[0] * 3)
            chunks.append(Chunk("code", section, "\n".join(lines[i + 1 : end - 1 if closed else end]), info, i + 1))
            i = end
            continue
        if i in headings and any(l.strip() for l in buf):
            flush()  # non-empty prose before a heading becomes its own chunk
        if not buf:
            buf_line = i + 1
        if i in headings:
            section = headings[i]
        buf.append(lines[i])
        i += 1
    flush()
    return chunks
