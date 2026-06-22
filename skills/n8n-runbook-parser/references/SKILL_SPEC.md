# SKILL.md Spec (reference)

> Preserved reference: this is the community skill-repo `SKILL.md` manifest spec.
> The `runbook-parser` `SKILL.md` is authored to conform to it. Kept here so the
> rules (and the 11 PR checks) stay discoverable on demand.

Every skill profile in this repository is described by a `SKILL.md` manifest,
validated by the PR check.

A skill lives in its own directory under one of two roots — `skills/` for
contributed skills, or `.github/skills/` for the repo's own operational
meta-skills. Both are validated against this spec the same way:

```
skills/<skill-name>/            # contributed skills
.github/skills/<skill-name>/    # the repo's own meta-skills
└── SKILL.md        # manifest (this spec)
```

## 1. Frontmatter (required)

The `SKILL.md` MUST begin with a YAML frontmatter block. These fields are
mandatory:

| Field         | Type   | Notes                                           |
| ------------- | ------ | ----------------------------------------------- |
| `name`        | string | Unique, kebab-case identifier for the skill.    |
| `description` | string | What the skill does and when it should trigger. |

**`name`** must be kebab-case — lowercase letters and digits in
hyphen-separated groups, with no leading, trailing, or consecutive hyphens
(`^[a-z0-9]+(-[a-z0-9]+)*$`) — at most **64 characters**, and must **exactly
match the skill's directory name** (so the manifest and the folder line up,
since consumers wire skills in by folder name).

**`description`** is the only metadata an agent sees when routing, so keep it
specific. It must be at most **1024 characters** and contain **no angle
brackets** (`<` or `>`), which would be misread as markup where the manifest is
injected.

Only the following frontmatter keys are allowed; any other key is rejected:
`name`, `description`, `owner`, `tags`, `license`, `allowed-tools`,
`compatibility`, `metadata`. Of these, `owner` and `tags` are recommended.

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
- Never <Y> (Why: <non-obvious reason>)

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

## 3. What the PR check enforces

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
11. **No cross-skill duplicates.** When the validator runs over more than one
    skill (e.g. `--all`, or a multi-skill diff in CI), it refuses two skills
    that share the same `name`, the same `description`, or the same normalised
    body (the part after the H1 title and the one-line summary). This catches
    copy-pasted manifests before they ship. Pass `--no-duplicates` to skip the
    check when you intentionally want to validate just one file in isolation.

### Gotchas the validator can't always pinpoint

- **Colons inside `description`.** YAML reads `key: value` as a mapping, so a
  description containing `: ` (colon + space) — e.g.
  `"Use when: planning a deployment"` — must be wrapped in single quotes so
  PyYAML doesn't try to split it. Double quotes also work, but then you have to
  escape any literal `"`.
- **Section headings use a straight ASCII apostrophe.** Write `## Don't Use
When` with `'` (U+0027), not the curly `'` (U+2019) some editors insert
  automatically. The validator normalises smart quotes before matching, so the
  canonical form in your file is the ASCII one.

Run the same check locally before opening a PR:

```bash
uv run python scripts/validate_skill.py skills/<your-skill>/SKILL.md
# or validate everything
uv run python scripts/validate_skill.py --all
```
