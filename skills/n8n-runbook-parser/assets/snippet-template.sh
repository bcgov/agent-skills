#!/usr/bin/env bash
# SNIPPET NAME — one line: the read-only triage info this collects, emitted as JSON.
#
# Cleaned from SOURCE NAME "SECTION" (read-only collection only).
# Params:    PARAM (env or $1, required) — describe it.
# Read-only: only READ-ONLY-COMMANDS; idempotent, safe to re-run any time.
# Output:    stdout JSON { describe the shape }.
set -euo pipefail

# Required params — fail fast if missing.
PARAM="${1:-${PARAM:?set PARAM or pass it as arg 1}}"

# Read-only collection, then emit JSON with jq (use jq for verbose/structured data).
# ... oc/psql/patronictl ... read-only only ...
jq -n --arg param "$PARAM" '{ param: $param }'
