#!/usr/bin/env bash
# bcgov/agent-skills installer (macOS / Linux)
#
# Installs an @bcgov/<skill-name> package from GitHub Packages and sets up
# everything needed to fetch it: GitHub CLI, auth scope, and project .npmrc.
#
# Usage (interactive):
#   ./install-skill.sh
#
# Usage (non-interactive, e.g. CI):
#   ./install-skill.sh <skill-name> [version]
#   ./install-skill.sh azure-networking 0.1.1

set -euo pipefail

SCOPE="@bcgov"
REGISTRY="https://npm.pkg.github.com"
REPO="bcgov/agent-skills"

# ----- output helpers (ASCII only so old terminals + Win pwsh stay happy) -----
if [ -t 1 ]; then
  C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'; C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_CYAN=$'\033[36m'; C_RESET=$'\033[0m'
else
  C_BOLD=''; C_DIM=''; C_RED=''; C_GREEN=''; C_YELLOW=''; C_CYAN=''; C_RESET=''
fi

step() { printf '%s==>%s %s%s%s\n' "$C_CYAN" "$C_RESET" "$C_BOLD" "$*" "$C_RESET"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '%s[OK]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s[!]%s  %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
err()  { printf '%s[X]%s  %s\n' "$C_RED" "$C_RESET" "$*" >&2; }

# Read a line from the controlling terminal when available so the script works
# under `bash <(curl ...)` and `curl | bash` invocations alike. Falls back to
# stdin when no tty is attached (e.g. plain CI).
_read_line() {
  if [ -r /dev/tty ]; then
    IFS= read -r "$1" < /dev/tty
  else
    IFS= read -r "$1"
  fi
}

prompt_default() {
  # prompt_default <message> [default] -> echoes the user's answer (or default)
  local msg="$1" def="${2:-}" reply=''
  if [ -n "$def" ]; then
    printf '%s [%s]: ' "$msg" "$def" >&2
    _read_line reply
    printf '%s' "${reply:-$def}"
  else
    printf '%s: ' "$msg" >&2
    _read_line reply
    printf '%s' "$reply"
  fi
}

confirm() {
  # confirm <message> [default y|n] -> returns 0 for yes, 1 for no
  local msg="$1" def="${2:-y}" reply=''
  while true; do
    printf '%s [y/n] (default %s): ' "$msg" "$def" >&2
    _read_line reply
    reply="${reply:-$def}"
    case "$reply" in
      [Yy]|[Yy][Ee][Ss]) return 0 ;;
      [Nn]|[Nn][Oo])     return 1 ;;
    esac
  done
}

prompt_choice() {
  # prompt_choice <message> <option1> <option2> ... -> echoes chosen 1-based index
  local msg="$1"; shift
  local count=$#
  local i=1
  for opt in "$@"; do
    printf '    %d) %s\n' "$i" "$opt" >&2
    i=$((i+1))
  done
  local reply=''
  while true; do
    printf '%s [1-%d]: ' "$msg" "$count" >&2
    _read_line reply
    case "$reply" in
      ''|*[!0-9]*) ;;
      *) if [ "$reply" -ge 1 ] && [ "$reply" -le "$count" ]; then
           printf '%s' "$reply"; return
         fi ;;
    esac
  done
}

have() { command -v "$1" >/dev/null 2>&1; }

# ----- step 1: prerequisites -----
require_npm() {
  if ! have npm; then
    err "npm not found. Install Node.js from https://nodejs.org/ first."
    exit 1
  fi
}

# ----- step 2: install gh if missing -----
ensure_gh() {
  if have gh; then
    ok "GitHub CLI present ($(gh --version | head -1))"
    return
  fi
  step "GitHub CLI not found. Attempting install..."
  local os
  os="$(uname -s)"
  case "$os" in
    Darwin)
      if have brew; then
        brew install gh
      else
        err "Homebrew not found. Install gh manually: https://github.com/cli/cli#installation"
        exit 1
      fi
      ;;
    Linux)
      if have apt-get; then
        info "Detected apt. Adding GitHub CLI repository (will prompt for sudo)..."
        (type -p curl >/dev/null) || sudo apt-get install -y curl
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
          | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
        sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
          | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        sudo apt-get update
        sudo apt-get install -y gh
      elif have dnf; then
        # Write the .repo file directly so this works on both dnf4 (RHEL 9,
        # older Fedora) and dnf5 (Fedora 41+, RHEL 10+). dnf5 removed the
        # `config-manager --add-repo` flag; the file-drop form is supported
        # on every dnf version and matches the official gh install docs.
        info "Detected dnf. Adding GitHub CLI repository (will prompt for sudo)..."
        (type -p curl >/dev/null) || sudo dnf install -y curl
        sudo curl -fsSL https://cli.github.com/packages/rpm/gh-cli.repo \
          -o /etc/yum.repos.d/gh-cli.repo
        sudo dnf install -y gh
      elif have pacman; then
        sudo pacman -S --noconfirm github-cli
      else
        err "No recognized package manager (apt/dnf/pacman). Install gh manually: https://github.com/cli/cli#installation"
        exit 1
      fi
      ;;
    *)
      err "Unsupported OS '$os'. Install gh manually: https://github.com/cli/cli#installation"
      exit 1
      ;;
  esac
  if ! have gh; then
    err "gh install completed but the binary is not on PATH. Open a new shell and re-run."
    exit 1
  fi
  ok "GitHub CLI installed"
}

# ----- step 3: gh auth with read:packages -----
ensure_gh_auth() {
  if ! gh auth status >/dev/null 2>&1; then
    step "Logging in to GitHub CLI (need read:packages scope)..."
    gh auth login -s read:packages -w
  elif ! gh auth status 2>&1 | grep -q "read:packages"; then
    # Note: `gh auth status` only prints token scopes for the CLI's own OAuth
    # token. For env-supplied tokens (GH_TOKEN / GITHUB_TOKEN / PAT), no
    # scopes are printed, so we may run `gh auth refresh` unnecessarily.
    # That's harmless -- refresh is a no-op when the scope is already there.
    step "Adding read:packages scope to existing gh login..."
    gh auth refresh -h github.com -s read:packages
  else
    ok "GitHub CLI authenticated with read:packages"
  fi
}

# ----- step 4: project .npmrc points @bcgov at GitHub Packages -----
ensure_npmrc() {
  local npmrc="${PWD}/.npmrc"
  local scope_line="${SCOPE}:registry=${REGISTRY}"
  local auth_line='//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}'
  if [ -f "$npmrc" ] && grep -qF "$scope_line" "$npmrc"; then
    ok "Project .npmrc already configured for ${SCOPE}"
    return
  fi
  step "Writing ${SCOPE} registry config to .npmrc"
  # If the existing file doesn't end in a newline, prepend one so our new
  # entries don't concatenate onto the last line.
  if [ -s "$npmrc" ] && [ "$(tail -c 1 "$npmrc" | od -An -c | tr -d ' ')" != '\n' ]; then
    printf '\n' >> "$npmrc"
  fi
  printf '%s\n%s\n' "$scope_line" "$auth_line" >> "$npmrc"
  ok "Updated $npmrc"
  info "Future 'npm install' calls need NODE_AUTH_TOKEN set."
  info "Get a fresh token any time with: NODE_AUTH_TOKEN=\$(gh auth token)"
}

# ----- step 5: package.json bootstrap -----
ensure_package_json() {
  if [ -f package.json ]; then return; fi
  if [ "${NON_INTERACTIVE:-0}" = "1" ]; then
    info "No package.json here; running 'npm init -y' (non-interactive)"
    npm init -y >/dev/null
    ok "Created package.json"
    return
  fi
  if confirm "No package.json here. Run 'npm init -y' first?" "y"; then
    npm init -y >/dev/null
    ok "Created package.json"
  fi
}

# ----- step 6: pick a skill -----
list_skills() {
  if ! gh api "repos/${REPO}/contents/skills" --jq '.[] | select(.type=="dir") | .name' 2>/dev/null; then
    return 1
  fi
}

choose_skill() {
  local picked="${1:-}"
  if [ -n "$picked" ]; then printf '%s' "$picked"; return; fi
  echo >&2
  info "Fetching available skills from ${REPO}..."
  local skills=""
  if skills="$(list_skills)"; then
    echo >&2
    info "Available skills:"
    while IFS= read -r s; do
      [ -z "$s" ] || printf '      - %s\n' "$s" >&2
    done <<EOF
$skills
EOF
    echo >&2
  else
    warn "Could not fetch skill list (network or auth issue). Enter the name manually."
  fi
  local name
  name="$(prompt_default "Which skill?" "")"
  if [ -z "$name" ]; then
    err "Skill name is required."
    exit 1
  fi
  printf '%s' "$name"
}

# ----- step 7: install -----
install_skill() {
  local name="$1" version="${2:-}" pkg
  if [ -n "$version" ]; then pkg="${SCOPE}/${name}@${version}"
  else                       pkg="${SCOPE}/${name}"
  fi
  step "Installing ${pkg}"
  NODE_AUTH_TOKEN="$(gh auth token)" npm install "$pkg"
  ok "Installed ${pkg}"
}

# ----- step 8: wire the skill into an agent -----
# Only Copilot + Claude Code load SKILL.md natively today via the
# agentskills.io standard. For everything else (Codex CLI, Cursor, Cline, ...)
# we offer a generic symlink so the user points their tool at the directory.
symlink_skill_into() {
  local dir="$1" name="$2"
  mkdir -p "$dir"
  local link="$dir/$name"
  if [ -L "$link" ] || [ -e "$link" ]; then
    if confirm "  $link already exists. Replace?" "y"; then
      rm -rf "$link"
    else
      info "  Left existing $link in place."
      return
    fi
  fi
  ln -s "$(pwd)/node_modules/${SCOPE}/${name}" "$link"
  ok "  Symlinked $link -> node_modules/${SCOPE}/${name}"
}

patch_vscode_settings() {
  local settings=".vscode/settings.json"
  local target="node_modules/${SCOPE}"
  mkdir -p .vscode
  if [ ! -f "$settings" ]; then
    cat > "$settings" <<EOF
{
  "chat.agentSkillsLocations": ["${target}"]
}
EOF
    ok "  Created $settings"
    return
  fi
  # Try a strict-JSON merge via Node (already required as a dependency).
  # If the file contains comments / trailing commas (valid JSONC but not JSON),
  # we don't risk silently dropping them -- print a manual snippet instead.
  local result
  result="$(node -e "
const fs = require('fs');
const p = '${settings}';
const t = '${target}';
try {
  const o = JSON.parse(fs.readFileSync(p, 'utf8'));
  const k = 'chat.agentSkillsLocations';
  if (!Array.isArray(o[k])) o[k] = [];
  if (!o[k].includes(t)) o[k].push(t);
  fs.writeFileSync(p, JSON.stringify(o, null, 2) + '\n');
  console.log('MERGED');
} catch (e) {
  console.log('SKIP');
}
" 2>/dev/null)"
  if [ "$result" = "MERGED" ]; then
    ok "  Updated $settings with chat.agentSkillsLocations"
  else
    warn "  $settings contains comments or invalid JSON; not editing automatically."
    info "  Add this entry manually:"
    info "      \"chat.agentSkillsLocations\": [\"${target}\"]"
  fi
}

wire_copilot() {
  local how
  how="$(prompt_choice "  How for Copilot?" \
    "Scope folder (recommended) -- add node_modules/${SCOPE} to chat.agentSkillsLocations" \
    "Per-skill symlink -- link into .github/skills/${SKILL}/")"
  case "$how" in
    1) patch_vscode_settings ;;
    2) symlink_skill_into ".github/skills" "${SKILL}" ;;
  esac
}

wire_claude() {
  local how
  how="$(prompt_choice "  How for Claude Code?" \
    "Project -- symlink into .claude/skills/${SKILL}/" \
    "Personal -- symlink into ~/.claude/skills/${SKILL}/" \
    "Session-only -- print the 'claude --add-dir' command")"
  case "$how" in
    1) symlink_skill_into ".claude/skills" "${SKILL}" ;;
    2) symlink_skill_into "${HOME}/.claude/skills" "${SKILL}" ;;
    3) echo
       info "  Run this in your Claude Code session:"
       info "      claude --add-dir \"\$(pwd)/node_modules/${SCOPE}\""
       ;;
  esac
}

wire_custom() {
  echo
  info "  Use this for Codex CLI, Cursor, Cline, or any agent that scans a fixed folder."
  local path
  path="$(prompt_default "  Folder to symlink into" "./skills")"
  symlink_skill_into "$path" "${SKILL}"
}

wire_up_agent() {
  echo
  step "Wire ${SKILL} into an agent?"
  local choice
  choice="$(prompt_choice "  Choose" \
    "GitHub Copilot (VS Code)" \
    "Claude Code" \
    "Custom location (Codex / Cursor / other)" \
    "Skip -- I'll wire it up manually")"
  case "$choice" in
    1) wire_copilot ;;
    2) wire_claude  ;;
    3) wire_custom  ;;
    4) info "  Skipped. Snippets: https://github.com/${REPO}#step-4-wire-it-into-your-agent" ;;
  esac
}

# ============================ main ============================
echo
printf '%sbcgov/agent-skills installer%s\n' "$C_BOLD" "$C_RESET"
printf '%sInstalls a skill from GitHub Packages with auth + registry setup in one pass.%s\n' "$C_DIM" "$C_RESET"
echo

# Capture original positional args BEFORE any function might mutate context.
# When the caller supplied a positional skill arg they want hands-off scripted
# behavior; ditto when there's no controlling terminal (plain CI). NON_INTERACTIVE=1
# silences the npm-init / version / wire-up prompts and accepts sensible defaults.
SKILL_ARG="${1:-}"
VERSION_ARG="${2:-}"
if [ -n "$SKILL_ARG" ] || { [ ! -r /dev/tty ] && [ ! -t 0 ]; }; then
  NON_INTERACTIVE=1
else
  NON_INTERACTIVE=0
fi
export NON_INTERACTIVE

require_npm
ensure_gh
ensure_gh_auth
ensure_npmrc
ensure_package_json

SKILL="$(choose_skill "$SKILL_ARG")"
VERSION="$VERSION_ARG"
if [ -z "$VERSION" ] && [ "$NON_INTERACTIVE" != "1" ]; then
  VERSION="$(prompt_default "Version (blank for latest)" "")"
fi

install_skill "$SKILL" "$VERSION"

# Skip the interactive wire-up step in non-interactive mode (scripted invocation
# or no TTY); reuse the same gate as the prompts above for consistency.
if [ "$NON_INTERACTIVE" != "1" ]; then
  wire_up_agent
fi

echo
ok "Done. Skill installed to node_modules/${SCOPE}/${SKILL}/"
echo
info "If you skipped the wire-up step, see Step 4 on:"
info "  https://github.com/${REPO}#step-4-wire-it-into-your-agent"
echo
