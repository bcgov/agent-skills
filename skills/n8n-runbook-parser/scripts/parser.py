#!/usr/bin/env python3
"""CLI entry point for RunbookParser (see the module comment below for the model)."""

# parser.py — RunbookParser: tangle code out of prose runbooks into
# version-controlled snippets (per source, losslessly) and detect drift so edits
# can be backported upstream.
#
# Setup Instructions:
#   1. Ensure Python 3.9+ is installed and on PATH.
#   2. Install dependencies (runs locally / in CI, not in the n8n container):
#        pip install pyyaml markdown-it-py
#   3. Run from the repo root, e.g.:
#        python tools/n8n/skills/runbook-parser/scripts/parser.py ingest
#
# It reads a `RunbookParser` config (default tools/n8n/config.yaml), decomposes
# each source document into ordered, typed raw snippets under `working_dir/<group>/`
# (+ an index sidecar), and records each source's drift state into the config's
# machine-owned `status:` block (the `spec:` block is read-only and never rewritten,
# so its comments are preserved).
#
# Commands:
#   ingest     doc -> raw snippets (+ a verbatim doc copy) + status        (default)
#   check      reconstruct + recompute seals; report drift (read-only; exit 2 = drift)
#   seal       record sha(doc + cleaned code, sans comments) + snapshot cleaned
#              (after cleaning)
#   diff       show how cleaned snippets diverged from their seal, to drive a doc
#              back-port
#   include    add hand-written cleaned snippet(s) to a source's `cleaned`, then
#              seal (one step)
#
# This file is the CLI entry point; the implementation lives in the sibling rb_*.py
# modules
# (rb_markdown, rb_model, rb_config, rb_reconstruct, rb_commands, rb_log).
# See ../SKILL.md and ../references/ for the full model.

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the sibling rb_*.py modules import cleanly regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rb_commands  # noqa: E402
from rb_config import load_config  # noqa: E402
from rb_log import RunbookError, die, set_quiet  # noqa: E402

_COMMANDS = {
  "ingest": rb_commands.cmd_ingest,
  "check": rb_commands.cmd_check,
  "seal": rb_commands.cmd_seal,
  "diff": rb_commands.cmd_diff,
  "include": rb_commands.cmd_include,
}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
  """Define and parse the CLI: a single command plus global flags."""
  default_config = "tools/n8n/config.yaml"
  parser = argparse.ArgumentParser(
    prog="parser.py",
    description="RunbookParser — decompose runbook docs into composable snippets.",
  )
  parser.add_argument(
    "--config", default=default_config, help=f"config path (default {default_config})"
  )
  parser.add_argument(
    "--group",
    action="append",
    metavar="GROUP",
    help="limit to sources in this group, by exact group name (repeatable)",
  )
  parser.add_argument(
    "--source",
    action="append",
    metavar="NAME",
    help="limit to the source with this exact unique name (repeatable)",
  )
  parser.add_argument(
    "--snippet",
    action="append",
    metavar="FILE",
    help="cleaned snippet file to associate with --source (for 'include'; repeatable)",
  )
  parser.add_argument(
    "--dry-run", action="store_true", help="show actions without writing"
  )
  parser.add_argument(
    "-q", "--quiet", action="store_true", help="suppress progress output"
  )
  parser.add_argument(
    "command",
    nargs="?",
    default="ingest",
    choices=list(_COMMANDS),
    help="ingest (default) | check | seal | diff | include",
  )
  return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
  """Entry point: parse args, load the config, and dispatch to the chosen command."""
  args = parse_args(argv)
  set_quiet(args.quiet)
  cfg = load_config(Path(args.config))
  try:
    return _COMMANDS[args.command](cfg, args)
  except RunbookError as e:
    die(str(e))
  return 0


if __name__ == "__main__":
  sys.exit(main())
