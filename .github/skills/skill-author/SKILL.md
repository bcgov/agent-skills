---
name: skill-author
description: Scaffolds a new skill profile in this repo and fills in the required SKILL.md structure when a contributor wants to add a skill.
owner: bcgov
tags: [meta, skills]
metadata:
  internal: true
---

# Skill Author

## Use When
- The user wants to add a brand-new skill to this repo.
- The user asks how to start, scaffold, or structure a `SKILL.md`.
- The user has an idea for a skill but doesn't know the required layout.

## Don't Use When
- The user wants to check an existing skill against the spec → use `skill-validator`.
- The user is editing prose in an existing, already-structured skill.

## Workflow
1. Before scaffolding, confirm no upstream catalogue already covers this use case. Search [The Agent Skills Directory](https://www.skills.sh/), the [Microsoft Agent Skills catalog](https://microsoft.github.io/skills/#agents), [`anthropics/skills`](https://github.com/anthropics/skills), and [`github/awesome-copilot`](https://github.com/github/awesome-copilot). If an upstream skill covers it, point the user there instead of scaffolding a duplicate; only proceed when the skill is genuinely BC Gov–specific (encodes BC Gov policies, internal services, regulatory requirements, or org-specific workflows).
2. Pick a kebab-case `<skill-name>` and create `skills/<skill-name>/`.
3. Create `skills/<skill-name>/SKILL.md`. Either copy an existing skill's `SKILL.md` as a starting point (e.g. [`skills/azure-networking/SKILL.md`](../../../skills/azure-networking/SKILL.md)) and rewrite the content, or write from scratch using [`spec/SKILL_SPEC.md`](../../../spec/SKILL_SPEC.md) as the structural reference.
4. Fill the frontmatter (`name`, `description`) and write the H1 title line.
5. Complete all seven sections: Use When, Don't Use When, Workflow, Rules, Examples, Edge Cases, References.
6. Run `uv run python scripts/validate_skill.py skills/<skill-name>/SKILL.md` and fix any errors.

## Rules
- Always run the upstream-catalogue check in Workflow step 1 before scaffolding. (Why: this repo is for BC Gov–specific skills; duplicating an upstream skill fragments the ecosystem, doubles the maintenance burden, and makes it ambiguous which one consumers should install. Reviewers will ask for the result of this check in the PR description.)
- Never invent a new section order or rename a section. (Why: the validator matches the seven section titles exactly and the PR check will fail.)
- Always keep `## Use When` as situational triggers (when to reach for this skill at all) and `## Workflow` as the numbered procedure (how to do the work). Never let a Use When bullet paraphrase a Workflow step — if a bullet starts with "Always ship…", "Set X to Y", or restates a procedural detail, it belongs in Workflow, not Use When. (Why: the two sections serve different reader intents — routing vs. execution — and duplicating content between them bloats the agent's context, makes routing fuzzier, and drifts out of sync on every edit.)

## Examples
- "I want to add a skill for looking up land parcels" → scaffold `skills/parcel-lookup/`, fill the template, validate.
- "How do I start a new skill profile?" → copy the template into a new skill dir and walk through the seven sections.

## Edge Cases
- If a `skills/<skill-name>/` folder already exists → confirm whether to edit it (route to the author flow on the existing files) rather than overwriting.
- If the user hasn't named the skill → propose a kebab-case name from the described purpose before scaffolding.

## References
For the upstream-catalogue check in step 1, search [The Agent Skills Directory](https://www.skills.sh/), [Microsoft Agent Skills](https://microsoft.github.io/skills/#agents), [`anthropics/skills`](https://github.com/anthropics/skills), and [`github/awesome-copilot`](https://github.com/github/awesome-copilot); the "Before adding a new skill" section of [CONTRIBUTING.md](../../../CONTRIBUTING.md) explains the policy in full.

See [spec/SKILL_SPEC.md](../../../spec/SKILL_SPEC.md) for the authoritative manifest spec.
