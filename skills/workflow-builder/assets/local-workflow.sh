#!/usr/bin/env bash
#
# <name>.local.sh — run this workflow on a developer's machine: the shell equivalent of the n8n
# workflow JSON this skill builds. Same read-only / idempotent stages, running the SAME
# tools/n8n/merge.sh and report.sh as the n8n nodes, so local and n8n stay in lockstep. Writes an
# HTML report to /tmp and prints a file:// URL.
#
#   n8n node                       local stage (below)
#   ----------------------------   ---------------------------------------------------------------
#   Execute-Command (collect)   →  run each collection snippet-*; its JSON -> MERGE_*
#   Merge snippets              →  merge.sh        (flat: snippet fields stay top-level)
#   Execute-Command (validate)  →  run each validator-* on merged; its verdict -> MERGE_<CHECK>
#   Merge validations           →  merge.sh -k     (keyed by check -> the .validations object)
#   Report                      →  report.sh       (assemble merged + {validations}, render chained)
#   Markdown -> Respond         →  view.sh         (HTML in /tmp, prints a file:// URL)
#
# Copy to tools/n8n/workflows/<name>.local.sh, fill the <-- markers, and shellcheck it. Progress
# goes to stderr (>&2) so it never mixes into stdout.
#
# Usage:  <ENV>=<value> ./<name>.local.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
N8N="$ROOT/tools/n8n"
GROUP="<group>"                                # <-- snippets/<group>
SNIPPETS="$N8N/snippets/$GROUP"
NAME="<name>"                                  # <-- page name (/tmp/n8n-report/NAME.html)

# Inputs: the snippets read whatever env they need (it is inherited by every child process).
# Optionally require one up front, e.g.:   : "${NAMESPACE:?set NAMESPACE}"

# The lib scripts (merge.sh/report.sh/render.sh/view.sh/utils.sh) are owned by the workflow-builder
# skill and must ALREADY be deployed beside this tree. This script does NOT self-sync — the agent
# checks/refreshes them with `scripts/sync.sh --config <config.yaml>` before a local run (or you can
# run that yourself). See the skill's SKILL.md. Fail fast if a required script is missing.
for lib in merge.sh report.sh view.sh; do
  [ -x "$N8N/$lib" ] || { echo "error: $N8N/$lib missing — run: workflow-builder/scripts/sync.sh --config $N8N/config.yaml" >&2; exit 1; }
done

# Run snippet/validator $1 (validators take the merged JSON on stdin); `|| true` so a failing step
# is simply absent — its data drops out and the conditional report renders whatever arrived.
snip() {
  echo "  - $1" >&2
  bash "$SNIPPETS/$1.sh" 2>/dev/null || true
}

# --- Collect: each snippet's JSON -> MERGE_* -> flat merge (fields stay top-level; the MERGE_
#     names are just unique labels here). One export per collection snippet.
echo "collecting..." >&2
export MERGE_ONE="$(snip "<collection-snippet>")" # <-- one export per collection snippet
export MERGE_TWO="$(snip "<collection-snippet>")"
merged="$(bash "$N8N/merge.sh")"
unset ${!MERGE_@}

# --- Validate (optional — delete this block if the workflow has no validators): each verdict ->
#     MERGE_<CHECK> -> keyed merge -> the .validations object (keyed by check name).
echo "validating..." >&2
export MERGE_CHECK="$(printf '%s' "$merged" | snip "<validator>")" # <-- MERGE_<CHECK> per validator
validations="$(bash "$N8N/merge.sh" -k)"
unset ${!MERGE_@}

# --- Report (chained): report.sh assembles merged + {validations} and renders the report(s),
#     chaining each as the next's .previous (first arg = top). DATA/VALS go base64, matching how
#     the n8n report node passes them.
echo "rendering report..." >&2
export DATA="$(printf '%s' "$merged" | base64 | tr -d '\n')"
export VALS="$(printf '%s' "$validations" | base64 | tr -d '\n')"
bash "$N8N/report.sh" "$GROUP" "<report>.md" \
  | bash "$N8N/view.sh" "$NAME"
