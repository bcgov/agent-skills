#!/usr/bin/env bash
# n8n-entrypoint.sh — start n8n with EVERY baked triage group's snippets dir on PATH, so the
# Execute-Command nodes can call snippets/validators by bare name (`snippet-cluster-status.sh`,
# `validator-pg-wal.sh`) for whatever groups are in the image — no per-group config anywhere. The
# lib scripts' dir (/opt/triage) is already on PATH via the image ENV; this adds each
# /opt/triage/snippets/<group>/ at startup. n8n inherits the result, and so does every `sh -c` it
# spawns to run a node command.
#
# Wired in as the image ENTRYPOINT:  ENTRYPOINT ["tini", "--", "/opt/triage/n8n-entrypoint.sh"]
# with  CMD ["n8n"]  — tini stays PID 1, this runs under it and exec's n8n. If a Deployment overrides
# `command`, either drop that override (use the image default) or mirror it there:
#   command: ["tini", "--", "/opt/triage/n8n-entrypoint.sh"]
#   args: ["n8n"]
set -euo pipefail

for d in /opt/triage/snippets/*/; do
  [ -d "$d" ] || continue # no groups baked yet -> the glob stays literal; skip it
  case ":$PATH:" in
    *":${d%/}:"*) ;;          # already on PATH
    *) PATH="${d%/}:$PATH" ;; # prepend this group's snippets dir
  esac
done
export PATH

exec "$@"
