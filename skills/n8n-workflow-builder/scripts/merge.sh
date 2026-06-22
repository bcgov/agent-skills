#!/usr/bin/env bash
# merge.sh — combine the JSON in the MERGE_* environment variables into one JSON object on stdout.
# Each MERGE_<KEY>=<json> holds one upstream node's output, so the merge node names its OWN inputs
# and nothing else in the workflow has to reference a node by name.
#
#   merge.sh        flat (jq -s add): spread every value's top-level keys into one object. The
#                   <KEY> names are just unique labels. Use to merge collection snippets so their
#                   fields stay top-level (.members, .connections, .wal, …).
#   merge.sh -k     keyed: nest each value under its key (MERGE_ stripped, lowercased) ->
#                   {"<key>": <value>}. Use to key validator verdicts by name — MERGE_CLUSTER=…
#                   -> {"cluster": …} — which is exactly the .validations shape.
#   merge.sh --b64  base64-decode each value first. n8n can't carry raw JSON in a command param
#                   (its quotes/spaces break the shell), so a merge node passes each stdout
#                   base64-encoded: MERGE_X={{ $('node').item.json.stdout.base64Encode() }}.
#   flags combine:  merge.sh -k --b64
#
# Empty or invalid MERGE_* values are skipped, so a failed upstream step is simply absent.
# No MERGE_* set -> "{}". Reads only the environment; writes only stdout.
set -euo pipefail

keyed=0
b64=0
for arg in "$@"; do
  case "$arg" in
    -k | --keyed) keyed=1 ;;
    --b64) b64=1 ;;
    *)
      echo "merge.sh: unknown argument: $arg (use -k for keyed, --b64 to base64-decode inputs)" >&2
      exit 2
      ;;
  esac
done

parts=()
for var in ${!MERGE_@}; do
  raw="${!var}"
  [ "$b64" -eq 1 ] && raw="$(printf '%s' "$raw" | base64 -d 2>/dev/null || true)"
  obj="$(printf '%s' "$raw" | jq -c . 2>/dev/null)" || continue # skip empty / non-JSON
  if [ "$keyed" -eq 1 ]; then
    key="$(printf '%s' "${var#MERGE_}" | tr '[:upper:]' '[:lower:]')"
    parts+=("$(jq -nc --arg k "$key" --argjson v "$obj" '{($k): $v}')")
  else
    parts+=("$obj")
  fi
done

printf '%s\n' "${parts[@]+"${parts[@]}"}" | jq -s 'add // {}'
