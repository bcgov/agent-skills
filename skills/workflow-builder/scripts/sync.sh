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
# except itself (the lib scripts; never pull.sh/push.sh, which live at the tree root, not here).
#
#   sync.sh [--check] [tree-root]
#     (no flag)   copy any missing/stale lib script into <tree-root>; report what changed
#     --check     write nothing; exit 1 if anything is out of sync (for CI or a pre-run guard)
#     tree-root   the dir holding snippets/ (default: the co-located tools/n8n, three levels up)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

check=0
target=""
for a in "$@"; do
  case "$a" in
    --check) check=1 ;;
    -*) echo "sync.sh: unknown arg: $a (use --check)" >&2; exit 2 ;;
    *) target="$a" ;;
  esac
done

# Default to the co-located tree root, but only trust it if it actually looks like one (has
# snippets/) — once the skill is installed elsewhere, the caller must pass the project's tree root.
target="${target:-$(cd "$HERE/../../.." 2>/dev/null && pwd || true)}"
if [ -z "$target" ] || [ ! -d "$target/snippets" ]; then
  echo "sync.sh: pass the triage tree root (the dir holding snippets/), e.g. sync.sh /repo/tools/n8n" >&2
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
