#!/usr/bin/env python3
"""Validate SKILL.md files against the agent-skills spec.

Usage:
  validate_skill.py path/to/SKILL.md [more ...]  # validate specific files
  validate_skill.py --all                        # validate every skill
  validate_skill.py --base origin/main           # validate skills changed vs base

All modes also flag cross-skill duplicates (name, description, and body
content below the H1/summary) so that a copy-pasted SKILL.md cannot ship
with another skill's metadata or body. Pass ``--no-duplicates`` to skip
that check.

Exit code 0 = all valid, 1 = one or more errors.

Frontmatter is parsed with PyYAML so the validator has no hand-rolled parser to
maintain.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys

import yaml

# --- Spec definition --------------------------------------------------------

REQUIRED_FRONTMATTER = ("name", "description")

# Every frontmatter key the spec recognises. Anything else is a typo or an
# attempt to smuggle in unsupported behaviour, so it is rejected. name +
# description are required; the rest are optional (owner/tags are this repo's
# own additions, the others come from the Agent Skills standard).
ALLOWED_FRONTMATTER = frozenset(
  {
    "name",
    "description",
    "owner",
    "tags",
    "license",
    "allowed-tools",
    "compatibility",
    "metadata",
  }
)

# A skill name is the kebab-case identifier that also names its directory and
# its npm package: lowercase letters/digits in hyphen-separated groups, with no
# leading, trailing, or consecutive hyphens.
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LEN = 64

# The description is the only metadata an agent sees when routing, so the
# standard caps it. Angle brackets are forbidden because the manifest is
# injected into prompts/markup where '<...>' is interpreted as a tag.
MAX_DESCRIPTION_LEN = 1024

# A SKILL.md must stay skimmable: it is loaded into the agent's context up front,
# so deep detail belongs in references/ that the agent pulls on demand. This is
# the agent-skills standard cap on the whole manifest.
MAX_SKILL_LINES = 500

# Section headings (## ...) that every skill body must contain, in spec order.
REQUIRED_SECTIONS = [
  "Use When",
  "Don't Use When",
  "Workflow",
  "Rules",
  "Examples",
  "Edge Cases",
  "References",
]

# Bundled resources live in these flat subdirectories, exactly one level deep.
RESOURCE_DIRS = ("scripts", "references", "assets")

# Skills live under two roots: contributed skills in skills/, and the repo's own
# operational meta-skills in .github/skills/. Both are validated identically.
SKILL_ROOTS = ("skills", ".github/skills")


# --- Frontmatter parsing ----------------------------------------------------


def parse_frontmatter(text: str):
  """Split a SKILL.md file into its frontmatter mapping and body.

  Args:
    text: The full contents of a SKILL.md file.

  Returns:
    A tuple of ``(frontmatter, body, errors)``: the parsed frontmatter mapping
    (or ``None`` if it could not be parsed), the markdown body that follows the
    closing fence, and a list of error strings describing any parse failures.
  """
  if not text.startswith("---"):
    return None, text, ["missing YAML frontmatter (file must start with '---')"]
  m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
  if not m:
    return None, text, ["frontmatter block is not closed with a second '---'"]
  fm_block, body = m.group(1), m.group(2)
  try:
    data = yaml.safe_load(fm_block)
  except yaml.YAMLError as exc:
    return None, body, [f"frontmatter is not valid YAML: {exc}"]
  if data is None:
    return {}, body, []
  if not isinstance(data, dict):
    return None, body, ["frontmatter must be a mapping of key: value pairs"]
  return {str(k): v for k, v in data.items()}, body, []


# --- Validation -------------------------------------------------------------


def validate_frontmatter(data) -> list:
  """Check the frontmatter against the spec's field rules.

  Confirms the required fields are present, that ``name`` is a well-formed
  kebab-case identifier within the length limit, that ``description`` is within
  its length limit and free of angle brackets, and that no unexpected keys are
  present.

  Args:
    data: The parsed frontmatter mapping, or ``None`` if parsing failed.

  Returns:
    A list of error strings, one per problem found. Empty when the frontmatter
    satisfies the spec (or when ``data`` is ``None``, since a parse error has
    already been reported upstream).
  """
  errors = []
  if data is None:
    return errors  # a parse error was already reported

  for field in REQUIRED_FRONTMATTER:
    val = data.get(field)
    if val is None or (isinstance(val, str) and not val.strip()):
      errors.append(f"frontmatter missing required field '{field}'")

  name = data.get("name")
  if isinstance(name, str) and name.strip():
    n = name.strip()
    if len(n) > MAX_NAME_LEN:
      errors.append(
        f"frontmatter 'name' is {len(n)} chars — exceeds the {MAX_NAME_LEN}-char limit"
      )
    if not NAME_RE.match(n):
      errors.append(
        "frontmatter 'name' must be kebab-case: lowercase letters and digits "
        "in hyphen-separated groups, with no leading, trailing, or consecutive "
        "hyphens"
      )

  desc = data.get("description")
  if isinstance(desc, str) and desc.strip():
    d = desc.strip()
    if len(d) > MAX_DESCRIPTION_LEN:
      errors.append(
        f"frontmatter 'description' is {len(d)} chars — exceeds the "
        f"{MAX_DESCRIPTION_LEN}-char limit"
      )
    if "<" in d or ">" in d:
      errors.append(
        "frontmatter 'description' must not contain angle brackets ('<' or '>')"
      )

  for key in data:
    if key not in ALLOWED_FRONTMATTER:
      errors.append(
        f"frontmatter has unexpected key '{key}' — allowed keys are: "
        f"{', '.join(sorted(ALLOWED_FRONTMATTER))}"
      )

  return errors


def _heading_positions(body: str):
  """Return the start offsets of every markdown heading in the body.

  Args:
    body: The markdown body of a SKILL.md file.

  Returns:
    A list of character offsets where ``#``..``######`` headings begin, in
    document order.
  """
  return [m.start() for m in re.finditer(r"^#{1,6}\s+.+$", body, re.MULTILINE)]


# Fenced code blocks open with three or more backticks (or tildes) as the
# first non-space content on a line. A `## ` inside such a fence is sample
# text, not a real markdown heading — masking the fence content before any
# regex scan keeps the structural checks from being fooled by it.
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _strip_code_fences(body: str) -> str:
  """Return ``body`` with fenced-code-block lines blanked to spaces.

  Byte offsets are preserved: every blanked line keeps its original length so
  that ``re.finditer(...).start()`` matches the same character index in the
  returned string and in the input body. The opening and closing fence lines
  are also blanked so an interior ``## comment`` cannot be matched as a real
  markdown heading by downstream regexes.

  Args:
    body: The markdown body of a SKILL.md file.

  Returns:
    A string of identical length and line count to ``body``, with every
    character inside (and on) a fenced code block replaced by a space.
  """
  lines = body.split("\n")
  in_fence = False
  for i, line in enumerate(lines):
    if _FENCE_RE.match(line):
      in_fence = not in_fence
      lines[i] = " " * len(line)
    elif in_fence:
      lines[i] = " " * len(line)
  return "\n".join(lines)


def _content_after(body: str, start: int, heads) -> str:
  """Return the text between a heading and the next section boundary.

  Args:
    body: The markdown body being inspected.
    start: The character offset of the heading whose content is wanted.
    heads: Section-boundary heading offsets in ``body``. Pass only the ``##``
      positions when checking whether a required section is empty, so that a
      sub-heading (``###`` and deeper) inside the section is treated as part
      of the section's content rather than as the section's end.

  Returns:
    The stripped text that follows the heading line up to the next boundary,
    or an empty string when the section has no content.
  """
  nxt = min([h for h in heads if h > start], default=len(body))
  line_end = body.find("\n", start)
  if line_end == -1 or line_end >= nxt:
    return ""
  return body[line_end + 1 : nxt].strip()


def validate_body(body: str) -> list:
  """Validate the markdown body against the structural spec.

  Confirms the body has an H1 title and that all seven required ``##`` sections
  are present and non-empty. Section titles are compared after normalising the
  Unicode right-single-quote ``'`` (U+2019) to the ASCII apostrophe ``'``
  (U+0027), so an editor that auto-converts the spec's canonical ``## Don't
  Use When`` heading into a curly-quote variant does not produce a spurious
  "missing required section" failure.

  Args:
    body: The markdown body that follows the frontmatter.

  Returns:
    A list of error strings describing every structural problem found; empty
    when the body conforms to the spec.
  """
  errors = []
  if not body.strip():
    return ["body is empty — it must contain the required sections"]

  # Strip fenced-code-block content before scanning for headings so that a
  # ``## comment`` inside a YAML / Bash / Terraform sample is not mistaken for
  # a markdown heading. Byte offsets are preserved so `m.start()` lines up
  # with the original `body` for content extraction below.
  scan_body = _strip_code_fences(body)

  # H1 title
  if not re.search(r"^#\s+(.+?)\s*$", scan_body, re.MULTILINE):
    errors.append("missing H1 title line '# <Skill Name>'")

  # required sections present + non-empty
  sections = [
    (m.start(), m.group(1).strip())
    for m in re.finditer(r"^##\s+(.+?)\s*$", scan_body, re.MULTILINE)
  ]
  # Only the ``##`` positions count as section boundaries. A required section
  # that opens with a ``###`` sub-heading (e.g. ``## Workflow`` followed by
  # ``### Step 1``) is still non-empty — its content runs until the next H2.
  section_starts = [s for s, _ in sections]
  # Normalise smart-quote apostrophe to ASCII before comparison so headings
  # like "## Don\u2019t Use When" still match the spec's "## Don't Use When".
  present = {title.replace("\u2019", "'").lower(): start for start, title in sections}
  required_lower = {s.replace("\u2019", "'").lower(): s for s in REQUIRED_SECTIONS}

  for req in REQUIRED_SECTIONS:
    if req.replace("\u2019", "'").lower() not in present:
      errors.append(f"missing required section '## {req}'")

  for start, title in sections:
    if title.replace("\u2019", "'").lower() in required_lower and not _content_after(
      body, start, section_starts
    ):
      errors.append(f"section '## {title}' is empty — add at least one line of content")

  return errors


def validate_length(text: str) -> list:
  """Check that a SKILL.md stays within the line budget.

  A skill manifest is loaded into the agent's context, so it must stay concise;
  detailed material belongs in ``references/`` linked from ``## References``.

  Args:
    text: The full contents of a SKILL.md file.

  Returns:
    A single-item error list when the file exceeds :data:`MAX_SKILL_LINES`,
    otherwise an empty list.
  """
  n = len(text.splitlines())
  if n > MAX_SKILL_LINES:
    return [
      f"SKILL.md is {n} lines — exceeds the {MAX_SKILL_LINES}-line limit; "
      "move detailed content into references/ and link it from '## References'"
    ]
  return []


def validate_name_matches_dir(data, skill_dir: str) -> list:
  """Check that the frontmatter ``name`` equals the skill's directory name.

  The name is the skill's identity — it must match the directory so the
  manifest and the folder line up (consumers wire skills in by folder name).

  Args:
    data: The parsed frontmatter mapping, or ``None`` if parsing failed.
    skill_dir: Path to the directory that holds the skill's ``SKILL.md``.

  Returns:
    A single-item error list when a valid ``name`` does not match the directory
    basename, otherwise an empty list.
  """
  if not isinstance(data, dict):
    return []
  name = data.get("name")
  if not isinstance(name, str) or not name.strip():
    return []
  dirname = os.path.basename(os.path.normpath(skill_dir))
  if name.strip() != dirname:
    return [
      f"frontmatter 'name' ('{name.strip()}') must match the skill directory "
      f"name ('{dirname}')"
    ]
  return []


def validate_resource_layout(skill_dir: str) -> list:
  """Check that bundled resource directories stay exactly one level deep.

  ``scripts/``, ``references/``, and ``assets/`` hold files the agent pulls on
  demand; nesting subdirectories under them breaks the flat, predictable layout
  the spec requires.

  Args:
    skill_dir: Path to the directory that holds the skill's ``SKILL.md``.

  Returns:
    A list of error strings, one per nested subdirectory found; empty when every
    resource directory is flat (or absent).
  """
  errors = []
  for sub in RESOURCE_DIRS:
    d = os.path.join(skill_dir, sub)
    if not os.path.isdir(d):
      continue
    for entry in sorted(os.listdir(d)):
      if os.path.isdir(os.path.join(d, entry)):
        errors.append(
          f"'{sub}/{entry}/' nests a subdirectory — keep {sub}/ flat "
          "(resources must be exactly one level deep)"
        )
  return errors


def validate_file(path: str) -> list:
  """Validate a single SKILL.md file against the spec.

  Args:
    path: Path to a ``SKILL.md`` file.

  Returns:
    A combined list of every frontmatter, body, and layout error found; empty
    when the skill is fully spec-compliant.
  """
  if not os.path.isfile(path):
    return [f"file not found: {path}"]
  # ``utf-8-sig`` transparently strips a leading BOM so editors that save
  # SKILL.md with one don't trip the ``startswith('---')`` frontmatter check.
  with open(path, encoding="utf-8-sig") as f:
    text = f.read()
  skill_dir = os.path.dirname(path)
  data, body, errors = parse_frontmatter(text)
  errors = list(errors)
  errors += validate_frontmatter(data)
  errors += validate_body(body)
  errors += validate_length(text)
  errors += validate_name_matches_dir(data, skill_dir)
  errors += validate_resource_layout(skill_dir)
  return errors


# --- Module discovery -------------------------------------------------------


def _manifest_for(path: str):
  """Return the SKILL.md manifest path a changed file belongs to, if any.

  Args:
    path: A repository-relative path from a git diff (forward-slash separated).

  Returns:
    The ``<root>/<skill>/SKILL.md`` path when ``path`` sits inside a skill
    directory under one of :data:`SKILL_ROOTS`, otherwise ``None``. Paths use
    forward slashes on every platform so they compare cleanly in sets and round
    trip through ``open()`` (which accepts ``/`` on Windows).
  """
  parts = path.strip().split("/")
  for root in SKILL_ROOTS:
    depth = root.count("/") + 1  # path components in the root prefix
    prefix = parts[:depth]
    if prefix == root.split("/") and len(parts) >= depth + 1:
      return f"{root}/{parts[depth]}/SKILL.md"
  return None


def discover_all() -> list:
  """Find every skill manifest in the repository.

  The spec fixes the layout at ``<root>/<skill>/SKILL.md`` (e.g.
  ``skills/azure-networking/SKILL.md``), so the glob is intentionally
  depth-one. A recursive glob would also pick up stray ``SKILL.md`` files
  inside a skill's own ``references/`` or ``scripts/`` directory and treat
  them as additional skills, which they aren't.

  Returns:
    A sorted list of ``SKILL.md`` paths found under every root in
    :data:`SKILL_ROOTS`. Paths use forward slashes on every platform so that
    callers see identical strings on Linux, macOS, and Windows.
  """
  found = []
  for root in SKILL_ROOTS:
    matches = glob.glob(f"{root}/*/SKILL.md")
    found.extend(m.replace(os.sep, "/") for m in matches)
  return sorted(found)


def changed_modules(base: str) -> list:
  """Map files changed versus a base ref to their skill manifests.

  Args:
    base: A git ref (e.g. ``origin/main``) to diff the current ``HEAD``
      against.

  Returns:
    A sorted list of ``<root>/<name>/SKILL.md`` paths for every skill touched
    by the diff whose manifest still exists on disk. Returns an empty list when
    ``git`` is not installed or otherwise unavailable, so the validator can run
    on hosts without git rather than crashing with a stack trace.
  """
  try:
    res = subprocess.run(
      ["git", "diff", "--name-only", f"{base}...HEAD"],
      capture_output=True,
      text=True,
    )
    if res.returncode != 0:
      # Fall back to a plain two-dot diff when the three-dot form fails (e.g.
      # because the merge-base cannot be found in a shallow clone).
      res = subprocess.run(
        ["git", "diff", "--name-only", base],
        capture_output=True,
        text=True,
      )
      if res.returncode != 0:
        print(
          f"git diff vs '{base}' failed (exit {res.returncode}); "
          f"validating no changed skills. stderr: {res.stderr.strip()}",
          file=sys.stderr,
        )
        return []
  except FileNotFoundError:
    print("git not found on PATH; cannot compute changed skills.", file=sys.stderr)
    return []
  modules = set()
  for line in res.stdout.splitlines():
    manifest = _manifest_for(line)
    if manifest:
      modules.add(manifest)
  return sorted(m for m in modules if os.path.isfile(m))


# --- Duplicate detection ---------------------------------------------------

# Everything before the first '## ' heading (the H1 line plus any one-line
# summary) is dropped from the body fingerprint. Contributors who copy an
# existing skill almost always remember to update the H1, but often leave
# the substantive sections (Use When, Workflow, Rules, ...) untouched; this
# strip keeps the dedup focused on that substantive content.
_PRE_H2_RE = re.compile(r"^.*?(?=^##\s)", re.DOTALL | re.MULTILINE)

# Whitespace runs are collapsed and the text is lowercased so trivial diffs
# (a stray blank line, a capitalised heading) do not hide a copy-paste.
_WS_RE = re.compile(r"\s+")


def _normalize_text(s: str) -> str:
  """Return a comparable fingerprint: lowercased, whitespace-collapsed, stripped."""
  return _WS_RE.sub(" ", s.lower()).strip()


def _body_fingerprint(body: str) -> str:
  """Return the body's '## section' content as a comparable fingerprint."""
  return _normalize_text(_PRE_H2_RE.sub("", body, count=1))


def _canonical_path(path: str) -> str:
  """Canonical form for cross-platform path identity (handles case + symlinks)."""
  return os.path.normcase(os.path.realpath(path))


def _load_skill_entry(path: str):
  """Read a SKILL.md and return its dedup fingerprints, or ``None`` on failure.

  Args:
    path: Path to a ``SKILL.md`` file.

  Returns:
    A mapping with the skill's normalized ``name``, ``desc_norm``, and
    ``body_norm`` fingerprints, or ``None`` if the file cannot be read.
  """
  try:
    with open(path, encoding="utf-8-sig") as f:
      text = f.read()
  except OSError:
    return None
  data, body, _ = parse_frontmatter(text)
  name = desc = ""
  if isinstance(data, dict):
    raw_name = data.get("name")
    raw_desc = data.get("description")
    if isinstance(raw_name, str):
      name = raw_name.strip()
    if isinstance(raw_desc, str):
      desc = raw_desc.strip()
  return {
    "name": name,
    "desc_norm": _normalize_text(desc),
    "body_norm": _body_fingerprint(body),
  }


def check_duplicates(targets, corpus=None) -> dict:
  """Find skills whose name, description, or body content duplicates another.

  Catches copy-paste mistakes where a contributor cloned an existing skill
  but forgot to rewrite the metadata or the body. The body comparison drops
  the H1 and summary preamble (which contributors usually do update) and
  only compares the substantive ``##`` sections, so a "renamed the title,
  kept the rest verbatim" copy is still caught.

  Args:
    targets: SKILL.md paths to report duplicate errors against.
    corpus: SKILL.md paths to compare ``targets`` against. Defaults to
      ``targets``. When validating a subset (e.g. a single new skill), pass
      the full repo set so the subset is also compared against the existing
      manifests, not just the other targets in the same run.

  Returns:
    A mapping ``path -> list[error]`` for every target that duplicates one
    or more skills in ``corpus``. Targets with no duplicates are omitted.
  """
  if corpus is None:
    corpus = list(targets)

  # Load each unique file once, keyed by canonical path. The first spelling
  # we see for a given canonical path is kept so the report uses a path that
  # matches what the caller would recognise.
  by_canonical = {}
  for path in list(corpus) + list(targets):
    if not os.path.isfile(path):
      continue
    cp = _canonical_path(path)
    if cp in by_canonical:
      continue
    entry = _load_skill_entry(path)
    if entry is None:
      continue
    by_canonical[cp] = {"original": path, **entry}

  # Group skills by each fingerprint. Empty fingerprints are skipped so that
  # two files with missing metadata do not "duplicate" each other via the
  # shared empty string.
  by_name, by_desc, by_body = {}, {}, {}
  for cp, e in by_canonical.items():
    if e["name"]:
      by_name.setdefault(e["name"], []).append(cp)
    if e["desc_norm"]:
      by_desc.setdefault(e["desc_norm"], []).append(cp)
    if e["body_norm"]:
      by_body.setdefault(e["body_norm"], []).append(cp)

  errors = {}
  for t in targets:
    ct = _canonical_path(t)
    e = by_canonical.get(ct)
    if e is None:
      continue
    target_errs = []

    name_dups = sorted(
      by_canonical[d]["original"] for d in by_name.get(e["name"], []) if d != ct
    )
    if name_dups:
      target_errs.append(
        f"frontmatter 'name' duplicates: {', '.join(name_dups)} — "
        "each skill must have a unique name"
      )

    desc_dups = sorted(
      by_canonical[d]["original"] for d in by_desc.get(e["desc_norm"], []) if d != ct
    )
    if desc_dups:
      target_errs.append(
        f"frontmatter 'description' duplicates: {', '.join(desc_dups)} — "
        "looks like a copy-paste; describe what makes this skill different"
      )

    body_dups = sorted(
      by_canonical[d]["original"] for d in by_body.get(e["body_norm"], []) if d != ct
    )
    if body_dups:
      target_errs.append(
        f"SKILL.md body content duplicates (H1/summary ignored): "
        f"{', '.join(body_dups)} — looks like a copy-paste; rewrite the "
        "Workflow/Rules/Examples for this skill"
      )

    if target_errs:
      errors[t] = target_errs

  return errors


# --- CLI --------------------------------------------------------------------


def main(argv=None) -> int:
  """Run the validator command-line interface.

  Parses arguments, selects the set of skills to validate (explicit paths,
  ``--all``, or ``--base <ref>``), validates each one, and prints a per-skill
  pass/fail report.

  Args:
    argv: Optional argument vector for testing; defaults to ``sys.argv`` when
      ``None``.

  Returns:
    ``0`` if every targeted skill passed, ``1`` if any skill failed validation.
  """
  # The pass/fail report uses U+2713 / U+2717. On Windows the default console
  # code page is cp1252, which can't encode those — Python raises
  # UnicodeEncodeError mid-print and the whole run aborts. Reconfigure both
  # stdio streams to UTF-8 with replacement so the script is portable.
  for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
      try:
        reconfigure(encoding="utf-8", errors="replace")
      except (OSError, ValueError):
        # Stream is detached, redirected to a non-TextIOWrapper, or otherwise
        # not reconfigurable — fall through; the print() calls below will
        # still work for ASCII output and only the check/cross glyphs may be
        # mojibake'd. That's a strictly better failure mode than aborting.
        pass
  p = argparse.ArgumentParser(description="Validate SKILL.md files against the spec.")
  p.add_argument("paths", nargs="*", help="specific SKILL.md files to validate")
  p.add_argument("--all", action="store_true", help="validate every skill in the repo")
  p.add_argument(
    "--base", help="validate skills changed vs this git ref (e.g. origin/main)"
  )
  p.add_argument(
    "--no-duplicates",
    action="store_true",
    help="skip cross-skill duplicate detection (name/description/body)",
  )
  args = p.parse_args(argv)

  if args.all:
    targets = discover_all()
  elif args.base:
    targets = changed_modules(args.base)
  else:
    targets = args.paths

  if not targets:
    print("No skills to validate.")
    return 0

  per_file = {t: validate_file(t) for t in targets}

  if not args.no_duplicates:
    # Always compare targets against the full repo so that validating a
    # subset (e.g. one new skill) still catches duplicates of skills that
    # were not in the explicit target list.
    corpus = sorted(set(targets) | set(discover_all()))
    for t, errs in check_duplicates(targets, corpus).items():
      per_file.setdefault(t, []).extend(errs)

  failed = 0
  for t in targets:
    errs = per_file.get(t, [])
    if errs:
      failed += 1
      print(f"✗ {t}")
      for e in errs:
        print(f"    - {e}")
    else:
      print(f"✓ {t}")

  print()
  if failed:
    print(f"{failed} skill(s) failed validation.")
    return 1
  print(f"All {len(targets)} skill(s) passed validation.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
