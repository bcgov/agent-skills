# bcgov/agent-skills installer (Windows / PowerShell)
#
# Installs an @bcgov/<skill-name> package from GitHub Packages and sets up
# everything needed to fetch it: GitHub CLI, auth scope, and project .npmrc.
#
# Usage (interactive):
#   .\install-skill.ps1
#
# Usage (non-interactive, e.g. CI):
#   .\install-skill.ps1 -Skill <skill-name> [-Version <version>]
#   .\install-skill.ps1 -Skill azure-networking -Version 0.1.1
#
# Works in Windows PowerShell 5.1 and PowerShell 7+. ASCII-only output so
# Windows PowerShell does not misparse the script under any code page.

#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Skill,
    [string]$Version
)

$ErrorActionPreference = 'Stop'
$Scope = '@bcgov'
$Registry = 'https://npm.pkg.github.com'
$Repo = 'bcgov/agent-skills'

# ----- output helpers (ASCII only) -----
function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Info($msg) { Write-Host "    $msg" }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[X]  $msg" -ForegroundColor Red }

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Read-WithDefault([string]$Message, [string]$Default) {
    if ($Default) {
        $reply = Read-Host "$Message [$Default]"
        if ([string]::IsNullOrWhiteSpace($reply)) { return $Default }
        return $reply
    }
    return Read-Host $Message
}

function Confirm-YesNo([string]$Message, [string]$Default = 'y') {
    while ($true) {
        $reply = Read-Host "$Message [y/n] (default $Default)"
        if ([string]::IsNullOrWhiteSpace($reply)) { $reply = $Default }
        switch -Regex ($reply) {
            '^(?i:y|yes)$' { return $true }
            '^(?i:n|no)$' { return $false }
        }
    }
}

function Select-Choice([string]$Message, [string[]]$Options) {
    $i = 1
    foreach ($opt in $Options) {
        Write-Host ("    {0}) {1}" -f $i, $opt)
        $i++
    }
    $max = $Options.Count
    while ($true) {
        $reply = Read-Host ("{0} [1-{1}]" -f $Message, $max)
        if ($reply -match '^\d+$') {
            $n = [int]$reply
            if ($n -ge 1 -and $n -le $max) { return $n }
        }
    }
}

# ----- step 1: prerequisites -----
function Confirm-Npm {
    if (-not (Test-Command 'npm')) {
        Write-Err 'npm not found. Install Node.js from https://nodejs.org/ first.'
        exit 1
    }
}

# ----- step 2: install gh if missing -----
function Confirm-Gh {
    if (Test-Command 'gh') {
        Write-Ok "GitHub CLI present"
        return
    }
    Write-Step 'GitHub CLI not found. Attempting install...'
    if (Test-Command 'winget') {
        winget install --id GitHub.cli -e --accept-package-agreements --accept-source-agreements
    }
    elseif (Test-Command 'choco') {
        choco install -y gh
    }
    elseif (Test-Command 'scoop') {
        scoop install gh
    }
    else {
        Write-Err 'No supported package manager found (winget, choco, scoop). Install gh manually: https://github.com/cli/cli#installation'
        exit 1
    }
    # winget often installs to a path that is not on the current session's PATH; refresh.
    $env:PATH = [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH', 'User')
    if (-not (Test-Command 'gh')) {
        Write-Err 'gh installed but is not on PATH yet. Close and reopen your shell, then re-run this script.'
        exit 1
    }
    Write-Ok 'GitHub CLI installed'
}

# ----- step 3: gh auth with read:packages -----
function Confirm-GhAuth {
    $null = & gh auth status 2>&1
    $loggedIn = ($LASTEXITCODE -eq 0)
    if (-not $loggedIn) {
        Write-Step 'Logging in to GitHub CLI (need read:packages scope)...'
        & gh auth login -s read:packages -w
        if ($LASTEXITCODE -ne 0) { Write-Err 'gh auth login failed.'; exit 1 }
        return
    }
    # Note: `gh auth status` only prints token scopes for the CLI's own OAuth
    # token. For env-supplied tokens (GH_TOKEN / GITHUB_TOKEN / PAT), no scopes
    # are printed, so we may run `gh auth refresh` unnecessarily. That's
    # harmless -- refresh is a no-op when the scope is already there.
    $status = (& gh auth status 2>&1) -join "`n"
    if ($status -notmatch 'read:packages') {
        Write-Step 'Adding read:packages scope to existing gh login...'
        & gh auth refresh -h github.com -s read:packages
        if ($LASTEXITCODE -ne 0) { Write-Err 'gh auth refresh failed.'; exit 1 }
    }
    else {
        Write-Ok 'GitHub CLI authenticated with read:packages'
    }
}

# ----- step 4: project .npmrc -----
function Confirm-Npmrc {
    $npmrc = Join-Path (Get-Location) '.npmrc'
    $scopeLine = "${Scope}:registry=$Registry"
    $authLine = '//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}'
    if (Test-Path $npmrc) {
        $existing = Get-Content $npmrc -Raw
        if ($existing -like "*$scopeLine*") {
            Write-Ok "Project .npmrc already configured for $Scope"
            return
        }
        # If the existing file doesn't end in a newline, append one so our new
        # entries don't concatenate onto the last line.
        if ($existing -and -not $existing.EndsWith("`n")) {
            [System.IO.File]::AppendAllText($npmrc, "`n")
        }
    }
    Write-Step "Writing $Scope registry config to .npmrc"
    Add-Content -Path $npmrc -Value $scopeLine
    Add-Content -Path $npmrc -Value $authLine
    Write-Ok "Updated $npmrc"
    Write-Info "Future 'npm install' calls need NODE_AUTH_TOKEN set."
    Write-Info 'Get a fresh token any time with: $env:NODE_AUTH_TOKEN = (gh auth token)'
}

# ----- step 5: package.json bootstrap -----
function Confirm-PackageJson {
    if (Test-Path 'package.json') { return }
    if ($script:NonInteractive) {
        Write-Info "No package.json here; running 'npm init -y' (non-interactive)"
        npm init -y | Out-Null
        Write-Ok 'Created package.json'
        return
    }
    if (Confirm-YesNo "No package.json here. Run 'npm init -y' first?" 'y') {
        npm init -y | Out-Null
        Write-Ok 'Created package.json'
    }
}

# ----- step 6: pick a skill -----
function Get-AvailableSkills {
    try {
        $json = & gh api "repos/$Repo/contents/skills" 2>$null
        if ($LASTEXITCODE -ne 0) { return @() }
        return ($json | ConvertFrom-Json) | Where-Object { $_.type -eq 'dir' } | Select-Object -ExpandProperty name
    }
    catch {
        return @()
    }
}

function Select-Skill([string]$Given) {
    if ($Given) { return $Given }
    Write-Host ''
    Write-Info "Fetching available skills from $Repo..."
    $skills = Get-AvailableSkills
    if ($skills.Count -gt 0) {
        Write-Host ''
        Write-Info 'Available skills:'
        foreach ($s in $skills) { Write-Host "      - $s" }
        Write-Host ''
    }
    else {
        Write-Warn 'Could not fetch skill list (network or auth issue). Enter the name manually.'
    }
    $name = Read-WithDefault 'Which skill?' ''
    if ([string]::IsNullOrWhiteSpace($name)) {
        Write-Err 'Skill name is required.'
        exit 1
    }
    return $name
}

# ----- step 7: install -----
function Install-Skill([string]$Name, [string]$Ver) {
    if ($Ver) { $pkg = "${Scope}/${Name}@${Ver}" }
    else { $pkg = "${Scope}/${Name}" }
    Write-Step "Installing $pkg"
    $env:NODE_AUTH_TOKEN = (& gh auth token).Trim()
    & npm install $pkg
    if ($LASTEXITCODE -ne 0) {
        Write-Err 'npm install failed'
        exit $LASTEXITCODE
    }
    Write-Ok "Installed $pkg"
}

# ----- step 8: wire the skill into an agent -----
# Only Copilot + Claude Code load SKILL.md natively today via the
# agentskills.io standard. For Codex CLI, Cursor, Cline, etc., we offer
# a generic symlink so the user names the folder their agent scans.
function New-SkillLink([string]$Dir, [string]$Name) {
    if (-not (Test-Path $Dir)) { New-Item -ItemType Directory -Path $Dir -Force | Out-Null }
    $link = Join-Path $Dir $Name
    if (Test-Path $link) {
        if (Confirm-YesNo "  $link already exists. Replace?" 'y') {
            Remove-Item -Path $link -Recurse -Force
        }
        else {
            Write-Info "  Left existing $link in place."
            return
        }
    }
    $target = Join-Path (Get-Location) "node_modules/${Scope}/${Name}"
    # Try SymbolicLink (needs Developer Mode or admin on Windows), fall back to
    # Junction (works without elevation for directories), then to a hard copy.
    try {
        New-Item -ItemType SymbolicLink -Path $link -Target $target -ErrorAction Stop | Out-Null
        Write-Ok "  Symlinked $link -> node_modules/${Scope}/${Name}"
        return
    }
    catch {}
    try {
        New-Item -ItemType Junction -Path $link -Target $target -ErrorAction Stop | Out-Null
        Write-Ok "  Junction $link -> node_modules/${Scope}/${Name}"
        return
    }
    catch {}
    Write-Warn '  Could not create symlink or junction (Developer Mode disabled?). Falling back to copy.'
    Copy-Item -Path $target -Destination $link -Recurse -Force
    Write-Ok "  Copied to $link"
    Write-Info '  Note: copy is a one-shot; re-run this script to refresh after future upgrades.'
}

function Set-VSCodeSettings {
    $settings = '.vscode/settings.json'
    $target = "node_modules/${Scope}"
    if (-not (Test-Path '.vscode')) { New-Item -ItemType Directory -Path '.vscode' | Out-Null }
    if (-not (Test-Path $settings)) {
        $obj = [ordered]@{ 'chat.agentSkillsLocations' = @($target) }
        ($obj | ConvertTo-Json -Depth 8) | Set-Content -Path $settings -Encoding UTF8
        Write-Ok "  Created $settings"
        return
    }
    try {
        $content = Get-Content $settings -Raw
        $obj = $content | ConvertFrom-Json
        $key = 'chat.agentSkillsLocations'
        $existing = @()
        if ($obj.PSObject.Properties[$key]) { $existing = @($obj.$key) }
        if ($existing -notcontains $target) {
            $existing += $target
            if ($obj.PSObject.Properties[$key]) {
                $obj.$key = $existing
            }
            else {
                $obj | Add-Member -NotePropertyName $key -NotePropertyValue $existing
            }
            ($obj | ConvertTo-Json -Depth 32) | Set-Content -Path $settings -Encoding UTF8
        }
        Write-Ok "  Updated $settings with chat.agentSkillsLocations"
    }
    catch {
        Write-Warn "  $settings contains comments or invalid JSON; not editing automatically."
        Write-Info '  Add this entry manually:'
        Write-Info ('      "chat.agentSkillsLocations": ["{0}"]' -f $target)
    }
}

function Invoke-WireCopilot([string]$Name) {
    $how = Select-Choice '  How for Copilot?' @(
        "Scope folder (recommended) -- add node_modules/${Scope} to chat.agentSkillsLocations",
        "Per-skill symlink -- link into .github/skills/${Name}/"
    )
    switch ($how) {
        1 { Set-VSCodeSettings }
        2 { New-SkillLink '.github/skills' $Name }
    }
}

function Invoke-WireClaude([string]$Name) {
    $how = Select-Choice '  How for Claude Code?' @(
        "Project -- symlink into .claude/skills/${Name}/",
        "Personal -- symlink into ~/.claude/skills/${Name}/",
        "Session-only -- print the 'claude --add-dir' command"
    )
    switch ($how) {
        1 { New-SkillLink '.claude/skills' $Name }
        2 { New-SkillLink (Join-Path $HOME '.claude/skills') $Name }
        3 {
            Write-Host ''
            Write-Info '  Run this in your Claude Code session:'
            Write-Info ("      claude --add-dir `"{0}/node_modules/{1}`"" -f (Get-Location).Path, $Scope)
        }
    }
}

function Invoke-WireCustom([string]$Name) {
    Write-Host ''
    Write-Info '  Use this for Codex CLI, Cursor, Cline, or any agent that scans a fixed folder.'
    $path = Read-WithDefault '  Folder to symlink into' './skills'
    New-SkillLink $path $Name
}

function Invoke-WireUpAgent([string]$Name) {
    Write-Host ''
    Write-Step "Wire $Name into an agent?"
    $choice = Select-Choice '  Choose' @(
        'GitHub Copilot (VS Code)',
        'Claude Code',
        'Custom location (Codex / Cursor / other)',
        "Skip -- I'll wire it up manually"
    )
    switch ($choice) {
        1 { Invoke-WireCopilot $Name }
        2 { Invoke-WireClaude  $Name }
        3 { Invoke-WireCustom  $Name }
        4 { Write-Info "  Skipped. Snippets: https://github.com/$Repo#step-4-wire-it-into-your-agent" }
    }
}

# ============================ main ============================
Write-Host ''
Write-Host 'bcgov/agent-skills installer' -ForegroundColor White
Write-Host 'Installs a skill from GitHub Packages with auth + registry setup in one pass.' -ForegroundColor DarkGray
Write-Host ''

Confirm-Npm
Confirm-Gh
Confirm-GhAuth
Confirm-Npmrc

# Capture original parameter binding BEFORE any function mutates $Skill /
# $Version. When -Skill was supplied the caller wants hands-off scripted
# behavior; ditto when running in a non-interactive host. $NonInteractive
# silences the npm-init / version / wire-up prompts and accepts sensible defaults.
$SkillProvided = $PSBoundParameters.ContainsKey('Skill')
$VersionProvided = $PSBoundParameters.ContainsKey('Version')
$script:NonInteractive = $SkillProvided -or -not [Environment]::UserInteractive -or [Console]::IsInputRedirected

Confirm-PackageJson

$Skill = Select-Skill $Skill
if (-not $VersionProvided -and -not $script:NonInteractive) {
    $Version = Read-WithDefault 'Version (blank for latest)' ''
}

Install-Skill $Skill $Version

# Skip the interactive wire-up step in non-interactive mode (scripted
# invocation or no TTY); reuse the same gate as the prompts above for consistency.
if (-not $script:NonInteractive) {
    Invoke-WireUpAgent $Skill
}

Write-Host ''
Write-Ok "Done. Skill installed to node_modules/$Scope/$Skill/"
Write-Host ''
Write-Info 'If you skipped the wire-up step, see Step 4 on:'
Write-Info "  https://github.com/$Repo#step-4-wire-it-into-your-agent"
Write-Host ''
