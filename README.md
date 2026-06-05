# agent-skills

**A shared, reusable catalogue of BC Government agent skill profiles.** Write a
good pattern once, and every team across the BC Gov ecosystem can build on it.

Each skill is validated against a common spec on every pull request and — once
merged — published as a versioned **npm package** you install and upgrade with
tooling you already use.

---

## Jump to what you need

| I want to… | Go to |
| ---------- | ----- |
| Understand why skills are structured this way | [Why this structure?](#why-this-structure) |
| Find my way around the repo | [Repository layout](#repository-layout) |
| Write and submit a new skill | [Add a skill](#add-a-skill) |
| Understand how releases ship | [How publishing works](#how-publishing-works) |
| Use a published skill in my agent | [Consume a skill](#consume-a-skill) |
| Run the validator and tooling locally | [Local development](#local-development) |

> New here? Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) for access
> requirements, then [`spec/SKILL_SPEC.md`](spec/SKILL_SPEC.md) for the full
> manifest contract.

---

## Why this structure?

A skill is, at its core, just instructions for an agent. Left to a free-form
body, those instructions **drift**: one skill buries the trigger in a paragraph,
another forgets the failure path, a third never says what *not* to do. The agent
is left inferring intent from prose — and inference is where agents get vague,
hesitant, or wrong.

The **seven required sections** turn open-ended prose into a fixed contract.
Each one answers a question the agent actually asks at runtime:

| Section | The question it answers for the agent |
| ------- | ------------------------------------- |
| **Use When** | Should the agent fire for *this* request? |
| **Don't Use When** | Is a *different* skill the better fit? |
| **Workflow** | What concrete steps and tools does the agent run? |
| **Rules** | What must the agent always / never do, and why? |
| **Examples** | What does a real invocation look like? |
| **Edge Cases** | What does the agent do when the happy path doesn't hold? |
| **References** | Where's the heavy detail it can pull on demand? |

Because every skill answers the same questions in the same order, the agent gets
a **concrete plan instead of an abstract description** — when to engage, which
sibling skill to defer to, the exact steps, and how to recover when a lookup
comes back empty.

That predictability is what makes the catalogue **composable**: a reviewer can
diff a skill against the spec, the validator can enforce it mechanically, and an
agent can load dozens of skills knowing each exposes the same surface. Structure
is what lets many teams contribute skills that still behave like one coherent
system.

---

## Repository layout

```
agent-skills/
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml              # validator tooling + dependencies (managed with uv)
├── Makefile
├── spec/
│   └── SKILL_SPEC.md           # the authoritative manifest spec
├── templates/
│   ├── SKILL.md                # copy this to start a new skill
│   └── package.json            # copy this — holds the skill's name + version
├── skills/
│   └── <skill-name>/           # contributed skills — the whole folder is bundled
│       ├── SKILL.md            # required, spec-compliant manifest
│       ├── package.json        # required, publishes the skill to npm
│       ├── scripts/            # optional, executable helpers
│       ├── references/         # optional, heavy detail
│       └── assets/             # optional, templates & resources
├── scripts/
│   └── validate_skill.py       # spec validator (used by CI + locally)
├── tests/
│   └── test_validate_skill.py
└── .github/
    ├── skills/                 # the repo's own meta-skills (validated, not published)
    │   ├── skill-author/
    │   ├── skill-validator/
    │   └── skill-release/
    └── workflows/
        ├── pr.yml              # lints + tests tooling, then validates changed skills on every PR
        └── publish.yml         # npm-publishes changed skills on merge to main
```

**Skills live under two roots:**

- **`skills/`** — contributed BC Gov domain skills. Validated *and* published to
  npm.
- **`.github/skills/`** — the repo's own meta-skills (the tools that scaffold,
  validate, and release skills). Validated the same way, but **never published**.

---

## Add a skill

1. **Copy the templates** into a new folder:
   ```bash
   mkdir -p skills/<your-skill>/references
   cp templates/SKILL.md skills/<your-skill>/SKILL.md
   cp templates/package.json skills/<your-skill>/package.json
   ```
2. **Fill in** the `SKILL.md` frontmatter and all seven sections — see
   [spec/SKILL_SPEC.md](spec/SKILL_SPEC.md).
3. **Set the package name and version** in `package.json`
   (`@bcgov/skill-<your-skill>`). This is the single source of truth for the
   published version — there is no `version` in `SKILL.md`.
4. **Validate locally:**
   ```bash
   uv run python scripts/validate_skill.py skills/<your-skill>/SKILL.md
   ```
5. **Open a PR.** The check validates your changed skill automatically.

---

## How publishing works

Each skill is its own npm package, and its **`package.json` version is the
single source of truth.** Bumping that version is what ships a release.

When a PR merges to `main`, the publish workflow:

1. Re-validates every skill.
2. Finds the skills the merge changed.
3. Reads `name` + `version` from each one's `package.json` and runs
   `npm publish` — **unless that exact version is already published**, in which
   case it's skipped.

A few things worth knowing:

- **The whole skill folder ships.** Everything under `skills/<name>/` —
  `SKILL.md`, `package.json`, and any `scripts/`, `references/`, or `assets/` —
  is bundled, with no `files` list to maintain. To keep scratch files out, add an
  optional `.npmignore` inside the folder (it must not exclude `SKILL.md`).
- **Where packages land:** GitHub Packages (`https://npm.pkg.github.com`) under
  the `@bcgov` scope, authenticated with the workflow's built-in `GITHUB_TOKEN` —
  no extra secrets.

> **Switching to the public npm registry** is a two-line change: drop the
> `registry`/`scope` from `actions/setup-node` in
> [`publish.yml`](.github/workflows/publish.yml) and the `publishConfig` from
> each `package.json`, then publish with an `NPM_TOKEN`. Upside: consumers install
> with no auth. Tradeoff: you give up GitHub Packages' tenant-scoped access
> control.

---

## Consume a skill

Skills install like any other npm dependency, so your existing
`npm` / `npx` / `npm update` flow manages them — upgrades included.

**1. Point the `@bcgov` scope at GitHub Packages** by adding an `.npmrc` next to
your agent's `package.json`:

```ini
@bcgov:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}
```

`${NODE_AUTH_TOKEN}` is read from the environment at install time, so the token
itself never lands on disk or in version control.

**2. Provide the token.** GitHub Packages requires authentication even for
public packages, so `NODE_AUTH_TOKEN` needs to be set with a credential that has
the `read:packages` scope. Pick whichever fits where the install runs:

- **Local development — use the [GitHub CLI](https://cli.github.com/).** No PAT
  to create, store, or rotate; the CLI already manages a token for you.

  *Prerequisite:* install and sign in to the GitHub CLI once
  ([install guide](https://github.com/cli/cli#installation)). On Windows:
  `winget install --id GitHub.cli`. On macOS: `brew install gh`. Then
  `gh auth login` to sign in. Verify with `gh auth status`.

  One-time, add the `read:packages` scope to the CLI's token:

  ```bash
  gh auth refresh -h github.com -s read:packages
  ```

  Then, in each shell session you install from:

  ```powershell
  # PowerShell
  $env:NODE_AUTH_TOKEN = gh auth token
  ```

  ```bash
  # bash / zsh
  export NODE_AUTH_TOKEN=$(gh auth token)
  ```

  `gh auth logout` revokes npm access at the same time — credential management
  stays in one place.

- **GitHub Actions (consuming workflow) — use the built-in `GITHUB_TOKEN`.** No
  secret to configure:

  ```yaml
  jobs:
    install-skills:
      runs-on: ubuntu-24.04
      permissions:
        contents: read
        packages: read
      steps:
        - uses: actions/checkout@v6
        - uses: actions/setup-node@v6
          with:
            node-version: "24"
        - run: npm ci
          env:
            NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  ```

**3. Install** — pin a version for reproducible pulls:

```bash
npm install @bcgov/skill-<name>@0.1.0
```

It installs to `node_modules/@bcgov/skill-<name>/` with `SKILL.md` plus whatever
else the skill ships, exactly as it lives in this repo. Point your agent's skills
loader at that directory — the on-disk layout is preserved, so there's no extra
wiring.

**4. Upgrade** — because skills are plain npm packages:

```bash
npm outdated @bcgov/skill-<name>        # see what's newer
npm update @bcgov/skill-<name>          # move within your semver range
npm install @bcgov/skill-<name>@0.2.0   # jump to an exact version
```

Use a semver range (e.g. `"^0.1.0"`) to pick up compatible updates on
`npm update`, or pin an exact version to freeze it. Your lockfile keeps installs
reproducible across the team.

---

## Local development

This project uses [uv](https://docs.astral.sh/uv/) — no `requirements.txt`, no
manual virtualenv. uv reads `pyproject.toml` and builds the environment on
demand, so these work on a fresh checkout:

```bash
make format     # auto-format Python (2-space indent, double quotes)
make lint       # lint Python (style, imports, docstrings)
make test       # run validator unit tests
make validate   # validate every skill
make pack       # dry-run each skill's npm package (no publish)
```
