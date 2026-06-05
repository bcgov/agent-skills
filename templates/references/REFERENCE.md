# Reference: my-skill-name

> **What goes here vs in SKILL.md.** `SKILL.md` is the agent's always-loaded
> manifest — keep it under 500 lines and focused on *when to fire* and *what to
> do at a high level*. Anything heavy that the agent only needs on demand belongs
> in this file (or a sibling under `references/`):
>
> - long step-by-step procedures with many branches,
> - lookup tables, error-code maps, schema definitions,
> - worked end-to-end examples,
> - API or SDK detail the agent should consult before generating code.
>
> The agent pulls this file in by following the `## References` link in
> `SKILL.md`, so make sure that link points here once you've added content.

## <Topic 1>

<Heavy detail goes here. Use real headings; the agent reads structured Markdown
better than prose walls.>

## <Topic 2>

<More detail. Add more files under `references/` (flat — no subdirectories) if
this one grows past a few hundred lines.>
