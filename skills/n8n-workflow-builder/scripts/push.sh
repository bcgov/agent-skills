#!/usr/bin/env bash
#
# push.sh — push local workflow JSON files to n8n, matched by name.
#
# Workflows are upserted by their "name": if your n8n account (the API key) already has a
# workflow with that name it is overwritten (PUT); otherwise it is created (POST). Ids are NOT
# tracked — they are looked up fresh each push and never written back, so the JSON in git stays
# clean (name/nodes/connections/settings) and each dev keeps their own copy under their account.
# The n8n API ignores "active" on create/update, so the workflow is activated or deactivated
# afterwards to match the file. Tags are not pushed (the public API only accepts them separately).
#
# Expects the n8n API reachable — a port-forward (oc port-forward svc/n8n 5678:5678) or set
# N8N_URL to the n8n route directly.
#
# Auth: create an API key in the n8n UI (Settings -> n8n API) and export
# N8N_API_KEY before running.

set -euo pipefail

if ((BASH_VERSINFO[0] < 4)); then
  echo "Error: bash >= 4 required" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
N8N_URL="${N8N_URL:-http://localhost:5678}"

# resolve_workflows_dir — where workflow JSON lives, in precedence order:
#   1. N8N_WORKFLOWS_DIR (explicit, wins)
#   2. workflows/ beside the RunbookParser config (--config / N8N_CONFIG) — so the skill's own copy
#      can be pointed at a project's tree from anywhere. Defaults to config.yaml next to this script,
#      which is where the deployed copy sits (beside snippets/ + workflows/), so deployed runs need
#      no config flag.
#   3. workflows/ next to this script (last resort; the checks below error clearly if it has no JSON)
resolve_workflows_dir() {
  if [[ -n "${N8N_WORKFLOWS_DIR:-}" ]]; then
    printf '%s\n' "$N8N_WORKFLOWS_DIR"; return
  fi
  local cfg="${CONFIG:-$SCRIPT_DIR/config.yaml}"
  if [[ -f "$cfg" ]]; then
    printf '%s\n' "$(cd "$(dirname "$cfg")" && pwd)/workflows"; return
  fi
  printf '%s\n' "$SCRIPT_DIR/workflows"
}

usage() {
  cat <<'EOF'
Usage: push.sh [--dry-run] [--config FILE] [file.json|directory ...]

Pushes workflow JSON files to n8n. Directory arguments expand to the .json
files inside them. With no arguments, pushes every .json file in the default
workflows directory (workflows/ beside the RunbookParser config).

Workflows are matched by "name": a same-named workflow in your n8n account is
overwritten, otherwise one is created. Ids are not tracked or written back. The
"active" flag is reconciled via the activate/deactivate endpoints. Tags are not pushed.

Options:
  --dry-run      Validate files and show what would happen without pushing
  --config FILE  RunbookParser config.yaml; the default workflows source is workflows/ beside it
  -h, --help     Show this help

Environment:
  N8N_URL            Base URL of n8n (default: http://localhost:5678)
  N8N_API_KEY        API key (required); create one in the n8n UI under Settings -> n8n API
  N8N_CONFIG         RunbookParser config.yaml (same as --config); workflows/ beside it is the default
  N8N_WORKFLOWS_DIR  Explicit workflows directory (overrides --config/N8N_CONFIG)
EOF
}

DRY_RUN=false
CONFIG="${N8N_CONFIG:-}"
targets=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --config) CONFIG="${2:?--config needs a path}"; shift ;;
    --config=*) CONFIG="${1#*=}" ;;
    -h|--help) usage; exit 0 ;;
    -*)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
    *) targets+=("$1") ;;
  esac
  shift
done

# An explicit --config/N8N_CONFIG must exist — don't silently fall back to a wrong workflows dir.
if [[ -n "$CONFIG" && ! -f "$CONFIG" ]]; then
  echo "Error: config not found: $CONFIG" >&2
  exit 1
fi

command -v jq >/dev/null 2>&1 || { echo "Error: jq is required" >&2; exit 1; }

if [[ -z "${N8N_API_KEY:-}" ]]; then
  echo "Error: N8N_API_KEY is not set" >&2
  echo "(create an API key in the n8n UI under Settings -> n8n API, then: export N8N_API_KEY=<key>)" >&2
  exit 1
fi

if [[ ${#targets[@]} -eq 0 ]]; then
  targets=("$(resolve_workflows_dir)")
fi

files=()
for t in "${targets[@]}"; do
  if [[ -d "$t" ]]; then
    shopt -s nullglob
    matches=("$t"/*.json)
    shopt -u nullglob
    if [[ ${#matches[@]} -eq 0 ]]; then
      echo "Warning: no .json files in $t" >&2
    fi
    files+=("${matches[@]}")
  else
    files+=("$t") # missing files are reported per-file below
  fi
done

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No workflow .json files to push (run pull.sh first?)" >&2
  exit 1
fi

# Fail fast with a useful hint when the port-forward isn't up.
curl -sS -o /dev/null --max-time 5 "$N8N_URL/healthz" || {
  echo "Error: cannot reach n8n at $N8N_URL — is the port-forward running?" >&2
  echo "  e.g. oc port-forward svc/n8n 5678:5678" >&2
  exit 1
}

# api METHOD PATH [extra curl args...] — prints the response body; on
# HTTP >= 400 prints n8n's error message to stderr and returns non-zero.
api() {
  local method="$1" path="$2"
  shift 2
  local response status body
  response="$(curl -sS -X "$method" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    -H "Accept: application/json" \
    -w $'\n%{http_code}' \
    "$@" \
    "$N8N_URL/api/v1$path")"
  status="${response##*$'\n'}"
  body="${response%$'\n'*}"
  if [[ ! "$status" =~ ^[0-9]+$ ]] || [ "$status" -ge 400 ]; then
    echo "Error: $method $path -> HTTP $status" >&2
    jq -r '.message // .' <<<"$body" >&2 2>/dev/null || printf '%s\n' "$body" >&2
    return 1
  fi
  printf '%s' "$body"
}

# The create/update endpoints reject unknown properties, so send only the writable fields. A node
# command may be stored as an ARRAY of lines (see pull.sh — keeps long merge/report commands
# diff-friendly in git); join it back into the single "\n" string n8n expects. Plain-string
# commands pass through untouched, so both forms work.
build_body() {
  jq -c '{name, nodes, connections, settings: (.settings // {})}
         + (if .staticData != null then {staticData} else {} end)
         | .nodes |= map(
             if (.parameters.command | type) == "array"
             then .parameters.command |= join("\n")
             else . end
           )' "$1"
}

# PUT/POST ignore "active", so reconcile via the dedicated endpoints. jq's
# // operator treats false as empty, so compare the raw .active values.
sync_active() {
  local f="$1" id="$2" name="$3" resp="$4" want have
  want="$(jq -r '.active' "$f")" # true / false / null when absent
  have="$(jq -r '.active' <<<"$resp")"
  if [[ "$want" == "null" || "$want" == "$have" ]]; then
    return 0
  fi
  if [[ "$want" == "true" ]]; then
    api POST "/workflows/$id/activate" >/dev/null || return 1
    echo "  activated: $name"
  else
    api POST "/workflows/$id/deactivate" >/dev/null || return 1
    echo "  deactivated: $name"
  fi
}

# find_id_by_name NAME — echo the id of the (first) workflow with exactly this name in the
# account the API key belongs to, or nothing. Paginates; warns on duplicates.
find_id_by_name() {
  local name="$1" cursor="" page ids query
  while :; do
    query=(-G --data-urlencode "limit=250")
    if [[ -n "$cursor" ]]; then query+=(--data-urlencode "cursor=$cursor"); fi
    page="$(api GET /workflows "${query[@]}")" || return 1
    ids="$(jq -r --arg n "$name" '.data[]? | select(.name == $n) | .id' <<<"$page")"
    if [[ -n "$ids" ]]; then
      if [[ "$(wc -l <<<"$ids")" -gt 1 ]]; then
        echo "  warning: multiple workflows named '$name'; overwriting the first" >&2
      fi
      head -n1 <<<"$ids"
      return 0
    fi
    cursor="$(jq -r '.nextCursor // empty' <<<"$page")"
    if [[ -z "$cursor" ]]; then return 0; fi
  done
}

push_file() {
  local f="$1" name body resp id
  if [[ ! -f "$f" ]]; then
    echo "  failed: $f (no such file)" >&2
    return 1
  fi
  if ! jq -e 'type == "object" and .name and .nodes and .connections' "$f" >/dev/null 2>&1; then
    echo "  skipped: $f (not a workflow export — expected name/nodes/connections)" >&2
    return 1
  fi

  name="$(jq -r '.name' "$f")"
  body="$(build_body "$f")"
  id="$(find_id_by_name "$name")" || { echo "  failed: $f (could not query n8n)" >&2; return 1; }

  if [[ "$DRY_RUN" == true ]]; then
    if [[ -n "$id" ]]; then
      echo "  would overwrite: $name ($id)"
    else
      echo "  would create: $name"
    fi
    return 0
  fi

  if [[ -n "$id" ]]; then
    resp="$(api PUT "/workflows/$id" -H 'Content-Type: application/json' --data-binary @- <<<"$body")" || {
      echo "  failed: $f" >&2
      return 1
    }
    echo "  overwrote: $name ($id)"
  else
    resp="$(api POST "/workflows" -H 'Content-Type: application/json' --data-binary @- <<<"$body")" || {
      echo "  failed: $f" >&2
      return 1
    }
    id="$(jq -r '.id' <<<"$resp")"
    echo "  created: $name ($id)"
  fi

  sync_active "$f" "$id" "$name" "$resp"
}

failures=0
for f in "${files[@]}"; do
  push_file "$f" || failures=$((failures + 1))
done

if ((failures > 0)); then
  echo "Completed with $failures failure(s) out of ${#files[@]} file(s)" >&2
  exit 1
fi
if [[ "$DRY_RUN" == true ]]; then
  echo "Dry run complete: ${#files[@]} file(s) would be pushed"
else
  echo "Pushed ${#files[@]} file(s)"
fi
