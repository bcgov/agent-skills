# agent-skills

**A shared, reusable catalogue of BC Government agent skill profiles.** Write a
good pattern once, and every team across BC Gov can build on it.

Every skill is validated against a common spec on every pull request. Once it
merges, the same change ships as a versioned **npm package** that you install
and upgrade with the npm tooling you already use.

Browse the live catalogue at **<https://bcgov.github.io/agent-skills/>**.

---

## Jump to what you need

| I want to… | Go to |
| ---------- | ----- |
| Understand why skills look the way they do | [Why this structure?](#why-this-structure) |
| Find my way around the repo | [Repository layout](#repository-layout) |
| Use a published skill in my agent | [Consume a skill](#consume-a-skill) |
| Write and submit a new skill | [Add a skill](#add-a-skill) |
| See how a merge becomes a release | [How publishing works](#how-publishing-works) |
| Run the validator and tooling locally | [Local development](#local-development) |

> New here? Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) for access and
> branch rules, then [`spec/SKILL_SPEC.md`](spec/SKILL_SPEC.md) for the full
> manifest contract.

---

## Why this structure?

A skill is, at its core, just instructions for an agent. Left to a free-form
body, those instructions drift. One skill buries the trigger inside a paragraph;
another forgets the failure path; a third never says what *not* to do. The
agent ends up inferring intent from prose, which is exactly where it starts to
guess.

The **seven required sections** turn open-ended prose into a fixed contract.
Each one answers a question the agent actually asks at runtime:

| Section | The question it answers for the agent |
| ------- | ------------------------------------- |
| **Use When** | Should I fire for *this* request? |
| **Don't Use When** | Is a *different* skill the better fit? |
| **Workflow** | What concrete steps and tools do I run? |
| **Rules** | What must I always / never do, and why? |
| **Examples** | What does a real invocation look like? |
| **Edge Cases** | What do I do when the happy path doesn't hold? |
| **References** | Where's the heavy detail I can pull on demand? |

Because every skill answers the same questions in the same order, the agent
loads a plan it can actually act on: when to engage, which sibling skill to
defer to, the exact steps, and the fallback when a lookup comes back empty.

Because every skill has the same shape, a reviewer can diff one against the
spec and the validator can check it automatically. An agent can load dozens of
them without relearning the layout each time, which is what lets many teams
contribute skills that still behave like one coherent system.

---

## Repository layout

Two roots for skills, plus the tooling that keeps them honest:

```
agent-skills/
├── README.md                       # you are here
├── CONTRIBUTING.md                 # access, branch rules, PR flow
├── pyproject.toml / uv.lock        # validator + test deps (managed with uv)
├── Makefile                        # make format / lint / test / validate / pack
├── .yamllint                       # workflow YAML style
│
├── spec/
│   └── SKILL_SPEC.md               # authoritative manifest spec
├── templates/
│   ├── SKILL.md                    # copy this to start a new skill
│   └── package.json                # copy this — holds the skill's name + version
│
├── skills/                         # contributed skills — validated AND published
│   └── <skill>/                    # one folder per skill (browse the live site for the catalogue)
│
├── scripts/
│   └── validate_skill.py           # the spec validator (CI + local)
├── tests/
│   └── test_validate_skill.py
│
├── docs/                           # static site published to GitHub Pages
│
└── .github/
    ├── CODEOWNERS                  # add ownership rules to gate review (see CONTRIBUTING.md)
    ├── dependabot.yml              # cadence + grouping + Conventional-Commit prefixes
    ├── pull_request_template.md
    ├── scripts/                    # helpers called from workflows
    ├── skills/                     # the repo's own meta-skills (validated, never published)
    │   └── <meta-skill>/
    └── workflows/                  # PR validation, publish-on-merge, docs deploy, Dependabot auto-merge, etc.
```

Worth flagging about the layout above:

- **`skills/` is what ships.** Each folder there is bundled and published to
  npm whenever its `package.json` `version` is bumped. Browse
  [the live catalogue](https://bcgov.github.io/agent-skills/) for the current
  set; the [`skills/`](skills/) directory is the authoritative source.
- **`.github/skills/` is internal.** The meta-skills in that directory follow
  the same spec, but they exist to help contributors. They're validated, never
  published.
- **`docs/` is the public catalogue.** Pushes to `main` that touch `docs/**`
  rebuild and deploy the site through the Pages workflow under
  [`.github/workflows/`](.github/workflows/).

---

## Consume a skill

Skills install like any other npm dependency, so your existing
`npm` / `npx` / `npm update` flow already manages them, upgrades included.

**1. Point the `@bcgov` scope at GitHub Packages** by adding an `.npmrc` next
to your agent's `package.json`:

```ini
@bcgov:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}
```

`${NODE_AUTH_TOKEN}` is read from the environment at install time, so the token
itself never lands on disk or in version control.

**2. Provide the token.** GitHub Packages requires authentication even for
public packages, so `NODE_AUTH_TOKEN` needs a credential with the
`read:packages` scope. Pick whichever fits where the install runs:

- **Local development: let the [GitHub CLI](https://cli.github.com/) manage
  it.** No PAT to create, store, or rotate; the CLI already holds a token for
  you.

  *Prerequisite:* install and sign in to the GitHub CLI once
  ([install guide](https://github.com/cli/cli#installation)). On Windows:
  `winget install --id GitHub.cli`. On macOS: `brew install gh`. Then
  `gh auth login` and verify with `gh auth status`.

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

  `gh auth logout` revokes npm access at the same time, so credential
  management stays in one place.

- **GitHub Actions (consuming workflow): use the built-in `GITHUB_TOKEN`.** No
  extra secret needed:

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

**3. Install.** Pin a version for reproducible pulls:

```bash
npm install @bcgov/skill-<name>@0.1.0
```

Or omit the version to track the `latest` dist-tag, which the publish
workflow updates on every release:

```bash
npm install @bcgov/skill-<name>
```

It installs to `node_modules/@bcgov/skill-<name>/` with `SKILL.md` plus
whatever else the skill ships, exactly as it lives in this repo. Point your
agent's skill loader at that directory; the on-disk layout is preserved, so
there's no extra wiring.

**4. Upgrade.** Because skills are plain npm packages:

```bash
npm outdated @bcgov/skill-<name>        # see what's newer
npm update @bcgov/skill-<name>          # move within your semver range
npm install @bcgov/skill-<name>@0.2.0   # jump to an exact version
```

Use a semver range (e.g. `"^0.1.0"`) to pick up compatible updates on
`npm update`, or pin an exact version to freeze it. Your lockfile keeps
installs reproducible across the team.

---

## Add a skill

Once you have access set up, the loop looks like this:

1. **Copy the templates** into a new folder:
   ```bash
   mkdir -p skills/<your-skill>/references
   cp templates/SKILL.md skills/<your-skill>/SKILL.md
   cp templates/package.json skills/<your-skill>/package.json
   ```
2. **Fill in** the `SKILL.md` frontmatter and all seven sections; see
   [`spec/SKILL_SPEC.md`](spec/SKILL_SPEC.md).
3. **Set the package name and version** in `package.json`
   (`@bcgov/skill-<your-skill>`, starting at `0.1.0`). The published version
   lives only here; there is no `version` field in `SKILL.md` for it to drift
   from.
4. **Validate locally:**
   ```bash
   uv run python scripts/validate_skill.py skills/<your-skill>/SKILL.md
   ```
5. **Open a PR from a branch in this repo** (forks are blocked by the
   `fork-gate` job). The PR check validates your changed skill automatically.

> **Heads-up:** check an upstream catalogue (Microsoft Agent Skills, Anthropic
> `anthropics/skills`, awesome-copilot) before adding a new skill. If your use
> case is already covered, point consumers at the upstream skill instead of
> duplicating it here. Full guidance in
> [`CONTRIBUTING.md`](CONTRIBUTING.md#before-adding-a-new-skill-check-upstream-catalogs-first).

---

## How publishing works

Each skill is its own npm package, and bumping `version` inside its
**`package.json`** is what ships a release.

When a PR merges to `main`, [`publish.yml`](.github/workflows/publish.yml):

1. Re-validates every skill.
2. Finds the skills the merge changed (via git diff).
3. Reads `name` + `version` from each one's `package.json` and runs
   `npm publish --tag latest` — **unless that exact version is already
   published**, in which case it's skipped. The `--tag latest` keeps the
   `latest` dist-tag pointed at whatever this run shipped, so consumers who
   `npm install @bcgov/skill-<name>` (no version) get the most recent release.

Three things shape how this works:

- **The whole skill folder ships.** Everything under `skills/<name>/` —
  `SKILL.md`, `package.json`, plus any `scripts/`, `references/`, or `assets/`
  — is bundled, with no `files` list to maintain. To keep scratch files out,
  add an optional `.npmignore` inside the folder (it must not exclude
  `SKILL.md`).
- **Where packages land:** GitHub Packages (`https://npm.pkg.github.com`)
  under the `@bcgov` scope, authenticated with the workflow's built-in
  `GITHUB_TOKEN`. No extra secrets.
- **Dependabot keeps the tooling current.** Grouped, Conventional-Commit-
  prefixed PRs (cadence and ecosystems in
  [`.github/dependabot.yml`](.github/dependabot.yml)). Green Dependabot PRs
  auto-squash-merge themselves; red ones stay red until a human fixes them.

> **Switching to the public npm registry** is a two-line change: drop the
> `registry`/`scope` from `actions/setup-node` in
> [`publish.yml`](.github/workflows/publish.yml) and the `publishConfig` from
> each `package.json`, then publish with an `NPM_TOKEN`. Upside: consumers
> install with no auth. Tradeoff: you give up GitHub Packages' tenant-scoped
> access control.

---

## Local development

This project uses [uv](https://docs.astral.sh/uv/). No `requirements.txt`,
no manual virtualenv. uv reads `pyproject.toml` and builds the environment on
demand, so these all work on a fresh checkout:

```bash
make setup      # pre-warm the uv-managed virtualenv (optional)
make format     # auto-format Python (2-space indent, double quotes)
make lint       # lint Python (ruff) AND workflow YAML (yamllint)
make test       # run the validator unit tests
make validate   # validate every skill against the spec
make pack       # dry-run each publishable skill's npm package (no publish)
```

Python style is enforced by [ruff](https://docs.astral.sh/ruff/) (2-space
indent, double quotes, docstring on every function; see `pyproject.toml`).
Workflow YAML under `.github/workflows/` is linted by
[yamllint](https://yamllint.readthedocs.io/) using `.yamllint` at the repo root.

The meta-skills under [`.github/skills/`](.github/skills/) are part of the
normal workflow. They take care of scaffolding, running the validator,
and cutting a release on your behalf. Use them the same way you'd use any
other skill in your agent. They're the fastest path from idea to a published
skill.
