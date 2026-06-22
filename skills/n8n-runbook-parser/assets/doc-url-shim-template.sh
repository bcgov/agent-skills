#!/usr/bin/env bash
# url-shim-<group>.sh — GENERATED per group from config.yaml (status.docs.topics) by the
# runbook-parser skill's scripts/doc_links.py. DO NOT EDIT BY HAND — edit the registry in
# config.yaml, then run scripts/doc_links.py. It lives in snippets/<group>/ and is SOURCED by that
# group's validators (a sibling file), so each group carries only its own doc links.
#
# A static table of official-docs URLs, baked at build time so a validator resolves a doc link
# by concept with NO yq/config at run time. Source it, then:
#   url="$(doc_url <aspect> <version>)"     # e.g. doc_url wal-archiving 17
#   url="$(doc_url <aspect> latest)"        # "latest" -> the newest version on file for it
# An unknown aspect/version warns on stderr and returns 1 (e.g. a URL pruned from the registry),
# leaving the URL empty so callers degrade gracefully. Uses warn() from utils.sh when the caller
# has sourced it; otherwise prints a plain stderr line.

declare -A __DOC_URLS=(
# @@TOPICS@@
)

_doc_url_miss() {
  local msg="doc_url: no registry entry for '${1:-?}' version '${2:-?}' (pruned or never added)"
  if declare -F warn >/dev/null 2>&1; then warn "$msg"; else printf '%s\n' "$msg" >&2; fi
}

# Version sort key: numeric versions compare as numbers; non-numeric (e.g. "latest") sort highest.
_doc_ver_num() { case "$1" in '' | *[!0-9]*) printf 999999 ;; *) printf '%s' "$1" ;; esac; }

# doc_url <aspect> [version]  ->  prints the URL on stdout, or warns + returns 1.
doc_url() {
  local aspect="${1:-}" version="${2:-latest}" key best="" bestn=-1 k n
  [ -n "$aspect" ] || {
    _doc_url_miss "" "$version"
    return 1
  }
  key="$aspect|$version"
  if [ -n "${__DOC_URLS[$key]:-}" ]; then
    printf '%s\n' "${__DOC_URLS[$key]}"
    return 0
  fi
  if [ "$version" = latest ]; then
    for k in "${!__DOC_URLS[@]}"; do
      [ "${k%%|*}" = "$aspect" ] || continue
      n="$(_doc_ver_num "${k#*|}")"
      if [ "$n" -gt "$bestn" ]; then
        bestn="$n"
        best="${__DOC_URLS[$k]}"
      fi
    done
    [ -n "$best" ] && {
      printf '%s\n' "$best"
      return 0
    }
  fi
  _doc_url_miss "$aspect" "$version"
  return 1
}
