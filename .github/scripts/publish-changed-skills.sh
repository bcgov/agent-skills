#!/usr/bin/env bash
# Publish skills under skills/ that changed between two commits.
#
# Reads two required env vars (so the workflow stays small and we don't have
# to template anything into the script body):
#   BEFORE_SHA  – commit main pointed at before the merge (github.event.before)
#   HEAD_SHA    – commit main now points at              (github.sha)
#
# Behaviour:
#   * Walks every skill directory touched in the diff.
#   * Skips directories without a package.json (validated-only meta-skills,
#     or files outside any skill dir).
#   * Skips skill@version pairs already published to the registry.
#   * Publishes with `--tag latest` so the `latest` dist-tag always points at
#     the just-shipped version alongside the immutable version coordinate.
#     Consumers can then `npm install @bcgov/<name>` (no version) to
#     track the most recent release.
#   * Keeps going after a per-skill failure and reports them all at the end,
#     then exits non-zero so the workflow turns red. (One bad skill should not
#     hide successful publishes of the others or stop them from running.)

set -uo pipefail

: "${BEFORE_SHA:?BEFORE_SHA is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

# Only the root skills/ tree is published; .github/skills/ holds meta-skills
# that are validated on PRs but never shipped.
mapfile -t changed < <(
  git diff --name-only "$BEFORE_SHA" "$HEAD_SHA" \
    | awk -F/ '$1 == "skills" && NF >= 2 { print "skills/" $2 }' \
    | sort -u
)

if [ "${#changed[@]}" -eq 0 ]; then
  echo "No skills changed; nothing to publish."
  exit 0
fi

failures=()
for dir in "${changed[@]}"; do
  if [ ! -f "$dir/package.json" ]; then
    echo "skip $dir: no package.json"
    continue
  fi

  name=$(node -p "require('./$dir/package.json').name")
  version=$(node -p "require('./$dir/package.json').version")

  if npm view "$name@$version" version >/dev/null 2>&1; then
    echo "skip $name@$version: already published"
    continue
  fi

  echo "publishing $name@$version (tag: latest)"
  if ! (cd "$dir" && npm publish --tag latest); then
    echo "::error::failed to publish $name@$version from $dir"
    failures+=("$name@$version ($dir)")
  fi
done

if [ "${#failures[@]}" -ne 0 ]; then
  echo
  echo "Publish failures:"
  for f in "${failures[@]}"; do
    echo "  - $f"
  done
  exit 1
fi
