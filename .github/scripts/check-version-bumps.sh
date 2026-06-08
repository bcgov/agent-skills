#!/usr/bin/env bash
# Fail the PR when a changed publishable skill's package.json version was not
# bumped. Pairs with publish-changed-skills.sh: that script silently skips an
# unbumped version on merge, this one stops the unbumped change from landing.
#
# Reads one required env var:
#   BASE_REF - git ref to diff against (e.g. origin/main)
#
# Behaviour:
#   * For every skills/<name>/ directory the PR touches (ANY file inside the
#     folder counts), compares the version in HEAD's package.json against the
#     version in BASE_REF's package.json.
#   * Fails (and lists every offender) when the versions are equal. Bumping
#     the version is what ships a release - see CONTRIBUTING.md > Versioning.
#   * Skips brand-new skills (no package.json in BASE_REF) - there is no
#     previous version to compare against.
#   * Skips skill dirs that no longer have a package.json on HEAD - the spec
#     validator catches that as a separate error.
#   * Meta-skills under .github/skills/ are never published, so this check
#     does not apply to them.

set -uo pipefail

: "${BASE_REF:?BASE_REF is required}"

# Only the root skills/ tree is published; .github/skills/ holds meta-skills
# that are validated on PRs but never shipped, so unbumped meta-skill edits
# are fine.
mapfile -t changed < <(
  git diff --name-only "$BASE_REF"...HEAD \
    | awk -F/ '$1 == "skills" && NF >= 2 { print "skills/" $2 }' \
    | sort -u
)

if [ "${#changed[@]}" -eq 0 ]; then
  echo "No publishable skills changed; version bump check skipped."
  exit 0
fi

failures=()
for dir in "${changed[@]}"; do
  pkg="$dir/package.json"

  if [ ! -f "$pkg" ]; then
    echo "skip $dir: no package.json on HEAD"
    continue
  fi

  if ! git cat-file -e "$BASE_REF:$pkg" 2>/dev/null; then
    echo "skip $dir: new skill (no package.json in $BASE_REF)"
    continue
  fi

  new_version=$(jq -r .version "$pkg")
  old_version=$(git show "$BASE_REF:$pkg" | jq -r .version)

  if [ "$new_version" = "$old_version" ]; then
    echo "::error file=$pkg::skill '$dir' changed but version is still $new_version - run 'npm version patch|minor|major' inside $dir to bump it"
    failures+=("$dir (version $new_version unchanged)")
  else
    echo "ok $dir: $old_version -> $new_version"
  fi
done

if [ "${#failures[@]}" -ne 0 ]; then
  echo
  echo "Version bump check failed for ${#failures[@]} skill(s):"
  for f in "${failures[@]}"; do
    echo "  - $f"
  done
  echo
  echo "Bump the version in each skill's package.json (npm version patch|minor|major)."
  echo "See CONTRIBUTING.md > Versioning."
  exit 1
fi

echo
echo "All ${#changed[@]} changed skill(s) have version bumps."
