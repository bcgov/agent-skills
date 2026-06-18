"""Tiny logging + error type shared across the runbook-parser modules.

Progress goes to stdout (suppressed by ``--quiet``), problems go to stderr, and a fatal
problem exits the process. Kept dependency-free so every other module can import it.
"""

from __future__ import annotations

import sys

_quiet = False


class RunbookError(Exception):
    """A recoverable, user-facing failure (bad config, unreachable source, ...).

    Commands raise it; ``main`` turns it into a clean ``error: ...`` message and exit 1
    rather than a traceback.
    """


def set_quiet(quiet: bool) -> None:
    """Toggle suppression of :func:`info` progress lines (the ``-q/--quiet`` flag)."""
    global _quiet
    _quiet = quiet


def info(msg: str) -> None:
    """Print a progress line to stdout unless quiet mode is on."""
    if not _quiet:
        print(msg)


def warn(msg: str) -> None:
    """Print a non-fatal warning to stderr (always shown, even in quiet mode)."""
    print(msg, file=sys.stderr)


def die(msg: str):
    """Print a fatal error to stderr and exit with status 1."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)
