---
name: skill-author
description: Scaffolds a new skill profile in this repo and fills in the required SKILL.md structure when a contributor wants to add a skill.
---

# Skill Author

## Use When
- The user wants to add a brand-new skill to this repo.
- The user asks how to start, scaffold, or structure a `SKILL.md`.
- The user has an idea for a skill but doesn't know the required layout.

## Don't Use When
- The user wants to check an existing skill against the spec → use `skill-validator`.
- The user wants to bump a version or publish → use `skill-release`.
- The user is editing prose in an existing, already-structured skill.

## Workflow
1. Pick a kebab-case `<skill-name>` and create `skills/<skill-name>/`.
2. Copy `templates/SKILL.md` and `templates/package.json` into that folder.
3. Fill the frontmatter (`name`, `description`) and write the H1 title line.
4. Complete all seven sections: Use When, Don't Use When, Workflow, Rules, Examples, Edge Cases, References.
5. Set the package `name` to `@bcgov/<skill-name>` (matching the manifest `name`) and `version` to `0.1.0` in `package.json`.
6. Run `uv run python scripts/validate_skill.py skills/<skill-name>/SKILL.md` and fix any errors.

## Rules
- Always set the new skill's starting `version` to `0.1.0` in `package.json`, never in the `SKILL.md` frontmatter. (Why: version lives only in package.json to avoid drift between two sources of truth.)
- Always keep the package `name` as `@bcgov/<skill-name>` — same as the folder and the manifest `name`. (Why: consumers wire skills into their agent by folder name; matching keeps `node_modules/@bcgov/<name>/` usable as-is with no rename step.)
- Never invent a new section order or rename a section. (Why: the validator matches the seven section titles exactly and the PR check will fail.)
- Always keep `## Use When` as situational triggers (when to reach for this skill at all) and `## Workflow` as the numbered procedure (how to do the work). Never let a Use When bullet paraphrase a Workflow step — if a bullet starts with "Always ship…", "Set X to Y", or restates a procedural detail, it belongs in Workflow, not Use When. (Why: the two sections serve different reader intents — routing vs. execution — and duplicating content between them bloats the agent's context, makes routing fuzzier, and drifts out of sync on every edit.)

## Examples
- "I want to add a skill for looking up land parcels" → scaffold `skills/parcel-lookup/`, fill the template, validate.
- "How do I start a new skill profile?" → copy the templates into a new skill dir and walk through the seven sections.

## Edge Cases
- If a `skills/<skill-name>/` folder already exists → confirm whether to edit it (route to the author flow on the existing files) rather than overwriting.
- If the user hasn't named the skill → propose a kebab-case name from the described purpose before scaffolding.

## References
See [spec/SKILL_SPEC.md](../../../spec/SKILL_SPEC.md) for the authoritative manifest spec and [templates/SKILL.md](../../../templates/SKILL.md) for the starting point.
