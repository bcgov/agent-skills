#!/usr/bin/env bash
# sync.sh — deploy this skill's canonical lib scripts to a triage tree root (the dir that holds
# snippets/), so the copy the n8n image bakes and the local workflow runs always matches the
# INSTALLED workflow-builder skill. The scripts have to sit at that root because each self-locates
# via $0 and sources utils.sh / render.sh / snippets/<group> relative to itself.
#
# This is the sync the skill runs when a dev iterates or runs a local workflow: the skill is the
# source of truth, this materializes/verifies the deployed copy beside the Dockerfile + snippets.
#
# Idempotent — only writes a script that is missing or differs. Deploys every *.sh in this dir
# except itself: the chain's lib scripts plus push.sh/pull.sh (the n8n API client). They all
# self-locate via $0, so they must run from the tree root beside snippets/ — which is where this
# lands them.
#
#   sync.sh [--check] [--config FILE | tree-root]
#     (no flag)      copy any missing/stale script into the tree root; report what changed
#     --check        write nothing; exit 1 if anything is out of sync (for CI or a pre-run guard)
#     --config FILE  the RunbookParser config.yaml — the SAME pointer push.sh/pull.sh take. Its
#                    directory is the tree root (where snippets/ + workflows/ live). Also N8N_CONFIG.
#     tree-root      the tree root directly (alternative to --config; default: config.yaml next to
#                    this script when deployed, else the co-located tools/n8n three levels up)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

check=0
target=""
config="${N8N_CONFIG:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --check) check=1 ;;
    --config) config="${2:?--config needs a path}"; shift ;;
    --config=*) config="${1#*=}" ;;
    -*) echo "sync.sh: unknown arg: $1 (use --config FILE [--check])" >&2; exit 2 ;;
    *) target="$1" ;;
  esac
  shift
done

# Resolve the tree root (the dir holding snippets/). A positional tree root wins; otherwise derive
# it from the config's directory (--config / N8N_CONFIG — the abs path comes from where config.yaml
# sits, by convention its own spec.root); otherwise fall back to a co-located default. An explicit
# but missing --config is a hard error, so a typo can't silently sync to the wrong tree.
if [ -z "$target" ]; then
  if [ -n "$config" ]; then
    [ -f "$config" ] || { echo "sync.sh: config not found: $config" >&2; exit 2; }
    target="$(cd "$(dirname "$config")" && pwd)"
  elif [ -f "$HERE/config.yaml" ]; then
    target="$HERE" # deployed beside config.yaml: self-sync
  else
    target="$(cd "$HERE/../../.." 2>/dev/null && pwd || true)"
  fi
fi
if [ -z "$target" ] || [ ! -d "$target/snippets" ]; then
  echo "sync.sh: could not locate the triage tree root (the dir holding snippets/)." >&2
  echo "  pass the RunbookParser config (its directory is the tree root), e.g.:" >&2
  echo "    sync.sh --config /repo/tools/n8n/config.yaml" >&2
  exit 2
fi

drift=0
for src in "$HERE"/*.sh; do
  name="$(basename "$src")"
  [ "$name" = "sync.sh" ] && continue # the deployer is not itself deployed
  dst="$target/$name"
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    continue # already in sync
  fi
  drift=1
  if [ "$check" -eq 1 ]; then
    echo "  out of sync: $name" >&2
  else
    cp "$src" "$dst"
    chmod +x "$dst"
    echo "  synced: $name -> $target/" >&2
  fi
done

if [ "$drift" -eq 0 ]; then
  echo "sync.sh: lib scripts in sync with the skill ($target)" >&2
elif [ "$check" -eq 1 ]; then
  echo "sync.sh: deployed lib scripts differ from the skill — run: sync.sh '$target'" >&2
  exit 1
fi
