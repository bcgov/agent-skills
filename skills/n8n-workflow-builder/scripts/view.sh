#!/usr/bin/env bash
#
# view.sh — turn a rendered Markdown report (stdin) into an HTML page under /tmp and print a
# file:// URL to open it in a browser. The local-dev equivalent of n8n's Markdown->HTML +
# Respond-to-Webhook: convert the report so a developer can click the path and read it.
#
#   render.sh report.md < data.json | view.sh [NAME]      # writes /tmp/n8n-report/NAME.html
#
# The page styles + renders the Markdown in the browser with marked.js + github-markdown-css
# from a CDN (so no local Markdown tooling is needed — just a browser with internet).
# Depends only on bash + base64. Sibling to render.sh; LOCAL ONLY — it is not used inside the
# n8n container (n8n uses its own Markdown node).

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: view.sh [NAME]   (Markdown on stdin)

Writes the rendered report to /tmp/n8n-report/NAME.html and prints a file:// URL to open it in
a browser (NAME defaults to "report").

Options:
  -h, --help   show this help
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then usage; exit 0; fi

NAME="$(printf '%s' "${1:-report}" | tr -c 'A-Za-z0-9._-' '-')"   # safe filename
command -v base64 >/dev/null 2>&1 || { echo "Error: base64 is required" >&2; exit 1; }

OUTDIR="/tmp/n8n-report"
OUT="$OUTDIR/$NAME.html"
mkdir -p "$OUTDIR"

# Embed the Markdown as base64 and decode+render it in the browser (avoids all HTML/JS escaping
# issues, and round-trips UTF-8 correctly via TextDecoder).
b64="$(base64 <<<"$(cat)" | tr -d '\n')"
cat > "$OUT" <<HTML
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$NAME</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css/github-markdown-light.css">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>body{margin:0;background:#fff}.markdown-body{box-sizing:border-box;max-width:880px;margin:0 auto;padding:32px}</style>
</head>
<body>
<article class="markdown-body" id="out">Rendering report…</article>
<script>
  var b64 = "$b64";
  var md = new TextDecoder().decode(Uint8Array.from(atob(b64), function (c) { return c.charCodeAt(0); }));
  document.getElementById("out").innerHTML = marked.parse(md);
</script>
</body>
</html>
HTML

echo "file://$OUT"
