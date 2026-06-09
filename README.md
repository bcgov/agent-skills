# agent-skills

**A shared, reusable catalogue of BC Government agent skill profiles.** Write a
good pattern once, and every team across BC Gov can build on it.

Every skill is validated against a common spec on every pull request. Once it
merges to `main`, it is immediately installable into any compatible agent with
one `npx skills add` command — no registry, no auth, no version pinning.

Browse the live catalogue at **<https://bcgov.github.io/agent-skills/>**.

---

## Jump to what you need

| I want to… | Go to |
| ---------- | ----- |
| Understand why skills look the way they do | [Why this structure?](#why-this-structure) |
| Find my way around the repo | [Repository layout](#repository-layout) |
| Install a skill into my agent | [Consume a skill](#consume-a-skill) |
| Write and submit a new skill | [Add a skill](#add-a-skill) |
| See how a merge reaches consumers | [How distribution works](#how-distribution-works) |
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
├── Makefile                        # make format / lint / test / validate
├── .yamllint                       # workflow YAML style
│
├── spec/
│   └── SKILL_SPEC.md               # authoritative manifest spec
│
├── skills/                         # contributed skills — the shared catalogue
│   └── <skill>/                    # one folder per skill (browse the live site)
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
    ├── skills/                     # the repo's own meta-skills (validated, not part of the public catalogue)
    │   └── <meta-skill>/
    └── workflows/                  # PR validation, docs deploy, Dependabot auto-merge, etc.
```

Worth flagging about the layout above:

- **`skills/` is the public catalogue.** Each folder there is what consumers
  install with `npx skills add`. Browse
  [the live catalogue](https://bcgov.github.io/agent-skills/) for the current
  set; the [`skills/`](skills/) directory is the authoritative source.
- **`.github/skills/` is internal.** The meta-skills in that directory follow
  the same spec, but they exist to help contributors. They're validated by the
  same PR check but are not part of the public catalogue.
- **`docs/` is the public catalogue site.** Pushes to `main` that touch
  `docs/**` rebuild and deploy the site through the Pages workflow under
  [`.github/workflows/`](.github/workflows/).

---

## Consume a skill

Skills install with the [`skills` CLI](https://skills.sh) (from
[vercel-labs/skills](https://github.com/vercel-labs/skills)). It clones this
repo, finds every `SKILL.md`, and copies the matching skill folders — plus
their `scripts/`, `references/`, and `assets/` — into the right location for
your agent.

```bash
# Install the whole catalogue into your current project (interactive picker
# for the target agent: GitHub Copilot, Claude Code, Cursor, Cline, etc.).
npx skills add bcgov/agent-skills

# Install just one skill, non-interactively, into GitHub Copilot.
npx skills add bcgov/agent-skills --skill azure-networking --agent github-copilot --yes

# Install globally (skill is available across all of an agent's projects).
npx skills add bcgov/agent-skills --skill azure-networking --agent claude-code --global

# List the skills available in this catalogue without installing anything.
npx skills add bcgov/agent-skills --list
```

The CLI handles everything: no `.npmrc`, no GitHub token, no registry config.
**Re-run any time to pick up newer versions** — the CLI re-copies the latest
`main`. Pin to a specific commit by using a GitHub URL:
`npx skills add https://github.com/bcgov/agent-skills/tree/<SHA>`.

For consumers who want to wire skills in manually, every skill is a self-
contained folder under [`skills/`](skills/) — copy it anywhere your agent
scans for skills.

---

## Add a skill

Once you have access set up, the loop looks like this:

1. **Create your skill folder** and copy an existing `SKILL.md` as a starting point:
   ```bash
   mkdir -p skills/<your-skill>/references
   cp skills/azure-networking/SKILL.md skills/<your-skill>/SKILL.md
   ```
   Then rewrite the frontmatter and body for your skill. See
   [`spec/SKILL_SPEC.md`](spec/SKILL_SPEC.md) for the required structure.
2. **Fill in** the `SKILL.md` frontmatter and all seven sections.
3. **Validate locally:**
   ```bash
   uv run python scripts/validate_skill.py skills/<your-skill>/SKILL.md
   ```
4. **Open a PR from a branch in this repo** (forks are blocked by the
   `fork-gate` job). The PR check validates your changed skill automatically.

> **Heads-up:** check an upstream catalogue (Microsoft Agent Skills, Anthropic
> `anthropics/skills`, awesome-copilot) before adding a new skill. If your use
> case is already covered, point consumers at the upstream skill instead of
> duplicating it here. Full guidance in
> [`CONTRIBUTING.md`](CONTRIBUTING.md#before-adding-a-new-skill-check-upstream-catalogs-first).

---

## How distribution works

There is no publish step. Skills ship the moment a PR merges to `main`:

- **`npx skills add` reads the repo directly.** It clones `bcgov/agent-skills`
  at `main` (or whatever ref the consumer pins to), walks the `skills/` tree
  for `SKILL.md` files, and copies the entire containing folder — manifest,
  `scripts/`, `references/`, `assets/`, everything — into the agent‑specific
  destination it picks for you. No registry, no auth, no version pinning
  metadata to maintain.
- **The PR check is the only gate.** Every change runs the validator on the
  skills it touches; merge-to-`main` requires the `results` aggregator to be
  green. Once a PR merges, the next `npx skills add` run sees the new content.
- **Dependabot keeps the tooling current.** Grouped, Conventional-Commit‑
  prefixed PRs (cadence and ecosystems in
  [`.github/dependabot.yml`](.github/dependabot.yml)). Green Dependabot PRs
  auto-squash-merge themselves; red ones stay red until a human fixes them.

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
```

Python style is enforced by [ruff](https://docs.astral.sh/ruff/) (2-space
indent, double quotes, docstring on every function; see `pyproject.toml`).
Workflow YAML under `.github/workflows/` is linted by
[yamllint](https://yamllint.readthedocs.io/) using `.yamllint` at the repo root.

The meta-skills under [`.github/skills/`](.github/skills/) are part of the
normal workflow. They take care of scaffolding new skills and running the
validator on your behalf. Use them the same way you'd use any other skill in
your agent — they're the fastest path from idea to a merged skill.
