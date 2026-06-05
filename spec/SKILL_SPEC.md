# SKILL.md Spec

Every skill profile in this repository is described by a `SKILL.md` manifest and
a `package.json`, both validated by the PR check.

A skill lives in its own directory under one of two roots — `skills/` for
contributed skills, or `.github/skills/` for the repo's own operational
meta-skills. Both are validated against this spec the same way; only the root
`skills/` tree is published to npm (the meta-skills stay internal to the repo):

```
skills/<skill-name>/            # contributed skills
.github/skills/<skill-name>/    # the repo's own meta-skills
├── SKILL.md        # manifest (this spec)
└── package.json    # published name + version
```

## 1. Frontmatter (required)

The `SKILL.md` MUST begin with a YAML frontmatter block. These fields are
mandatory:

| Field         | Type   | Notes                                            |
| ------------- | ------ | ------------------------------------------------ |
| `name`        | string | Unique, kebab-case identifier for the skill.     |
| `description` | string | What the skill does and when it should trigger.  |

**`name`** must be kebab-case — lowercase letters and digits in
hyphen-separated groups, with no leading, trailing, or consecutive hyphens
(`^[a-z0-9]+(-[a-z0-9]+)*$`) — at most **64 characters**, and must **exactly
match the skill's directory name** (so the manifest, the folder, and the npm
package all line up).

**`description`** is the only metadata an agent sees when routing, so keep it
specific. It must be at most **1024 characters** and contain **no angle
brackets** (`<` or `>`), which would be misread as markup where the manifest is
injected.

Only the following frontmatter keys are allowed; any other key is rejected:
`name`, `description`, `owner`, `tags`, `license`, `allowed-tools`,
`compatibility`, `metadata`. Of these, `owner` and `tags` are recommended.

> The published **version is not in the frontmatter** — it lives in
> `package.json` (see §4) as the single source of truth.

```yaml
---
name: example-skill
description: One line on what this does and when it fires.
owner: your-team
tags: [example]
---
```

## 2. Body (required)

After the frontmatter, the body MUST contain — in this order — an H1 title
followed by all seven `##` sections. Each section must have at least one line of
content.

```markdown
# <Skill Name>

## Use When
- <specific situation>

## Don't Use When
- <adjacent case> → <other skill>

## Workflow
1. <step + tool>
2. ...

## Rules
- Always <X>
- Never <Y>  (Why: <non-obvious reason>)

## Examples
- "<user phrasing>" → <action>

## Edge Cases
- If <lookup empty> → <fallback>

## References
See [references/REFERENCE.md](references/REFERENCE.md) for <heavy detail>
```

### Keep it short — 500 lines max

A `SKILL.md` is loaded into the agent's context up front, so it must stay
skimmable. The manifest is capped at **500 lines** (the whole file, frontmatter
included). When a skill needs deeper material — long procedures, lookup tables,
worked examples, API detail — put it in a `references/` file the agent pulls on
demand, and link it from the `## References` section. The validator fails any
manifest over the cap.

### Keep bundled resources flat — one level deep

Skills may ship `scripts/`, `references/`, and `assets/` directories beside the
`SKILL.md`. These must stay **exactly one level deep** — flat files only, no
nested subdirectories (e.g. `references/REFERENCE.md`, not
`references/api/v1/REFERENCE.md`). A flat layout keeps on-demand resources
predictable for the agent to locate. The validator fails any nested resource
directory.

## 3. package.json (required for published skills)

A contributed skill under `skills/` ships as a versioned npm package, so it MUST
include a `package.json` beside its `SKILL.md`. The repo's own meta-skills under
`.github/skills/` are never published, so a `package.json` is **optional** there
— and validated only when one is present. These fields are mandatory whenever a
`package.json` exists:

| Field     | Type   | Notes                                                       |
| --------- | ------ | ----------------------------------------------------------- |
| `name`    | string | The package name, scoped — `@bcgov/skill-<skill-name>`.     |
| `version` | string | Semver (`MAJOR.MINOR.PATCH`). The source of truth for releases. |

```json
{
  "name": "@bcgov/skill-example-skill",
  "version": "0.1.0",
  "publishConfig": { "registry": "https://npm.pkg.github.com" }
}
```

**The entire skill directory is bundled automatically.** Everything under
`skills/<skill-name>/` — `SKILL.md`, plus any `scripts/`, `references/`,
`assets/`, or other files — ships in the package. Do **not** add a `files` field:
that turns npm into a whitelist and would silently drop directories. To exclude
scratch files, add an optional `.npmignore` inside the skill folder (it must not
exclude `SKILL.md`).

The publish workflow reads `name` + `version` from this file and skips any
version already published. Bumping `version` is what ships a new release — see
[CONTRIBUTING.md](../CONTRIBUTING.md) for the `npm version` flow.

## 4. What the PR check enforces

For each **changed** skill the validator confirms:

1. The `SKILL.md` starts with a closed YAML frontmatter block that parses as a
   mapping.
2. `name` and `description` are present and non-empty.
3. `name` is kebab-case, at most 64 characters, and **matches the skill's
   directory name**.
4. `description` is at most 1024 characters and contains no angle brackets.
5. No unexpected frontmatter keys are present (only `name`, `description`,
   `owner`, `tags`, `license`, `allowed-tools`, `compatibility`, `metadata`).
6. The body has an H1 title.
7. All seven required sections are present: **Use When**, **Don't Use When**,
   **Workflow**, **Rules**, **Examples**, **Edge Cases**, **References**.
8. None of those required sections is empty.
9. The whole `SKILL.md` is at most 500 lines.
10. Any bundled `scripts/`, `references/`, or `assets/` directory is flat — no
    nested subdirectories.
11. For a published skill under `skills/`, a `package.json` sits beside the
    manifest with a valid `name` and a semver `version`, and does **not** pin a
    `files` whitelist (the whole directory bundles automatically). For a
    meta-skill under `.github/skills/`, a missing `package.json` is allowed; if
    one is present it is held to the same rules.

Run the same check locally before opening a PR:

```bash
uv run python scripts/validate_skill.py skills/<your-skill>/SKILL.md
# or validate everything
uv run python scripts/validate_skill.py --all
```
