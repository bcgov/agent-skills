#!/usr/bin/env bash
# utils.sh — standard messaging for the tools/n8n shell helpers. SOURCE it; don't execute it:
#
#   . "$(dirname "$0")/utils.sh"          # local: sibling of view.sh / render.sh
#   . "$(command -v utils.sh)"            # n8n image: installed on PATH (/usr/local/bin)
#
# Everything prints to STDERR so stdout stays clean for JSON / pipes (snippets, render.sh).
#   info  — progress / neutral note        warn — non-fatal problem
#   err   — error (no exit)                 die  — error + exit 1
#   have  — is a command on PATH?           (use for soft dependency checks)
# Set N8N_LOG_TAG to prefix every line with "<tag>: " (e.g. the calling script's name).
# Idempotent and side-effect-free to source; safe to source more than once.

: "${N8N_LOG_TAG:=}"

_n8n_emit() { # _n8n_emit LEVEL_PREFIX MESSAGE...
  local level="$1"
  shift
  printf '%s%s%s\n' "${N8N_LOG_TAG:+$N8N_LOG_TAG: }" "$level" "$*" >&2
}

info() { _n8n_emit "" "$@"; }
warn() { _n8n_emit "warning: " "$@"; }
err() { _n8n_emit "error: " "$@"; }
die() {
  err "$@"
  exit 1
}
have() { command -v "$1" >/dev/null 2>&1; }
