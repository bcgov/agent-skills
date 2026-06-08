#!/usr/bin/env python3
"""Validate SKILL.md files against the agent-skills spec.

Usage:
  validate_skill.py path/to/SKILL.md [more ...]  # validate specific files
  validate_skill.py --all                        # validate every skill
  validate_skill.py --base origin/main           # validate skills changed vs base

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


def _content_after(body: str, start: int, heads) -> str:
  """Return the text between a heading and the next heading.

  Args:
    body: The markdown body being inspected.
    start: The character offset of the heading whose content is wanted.
    heads: All heading offsets in ``body`` (from :func:`_heading_positions`).

  Returns:
    The stripped text that follows the heading line up to the next heading, or
    an empty string when the section has no content.
  """
  nxt = min([h for h in heads if h > start], default=len(body))
  line_end = body.find("\n", start)
  if line_end == -1 or line_end >= nxt:
    return ""
  return body[line_end + 1 : nxt].strip()


def validate_body(body: str) -> list:
  """Validate the markdown body against the structural spec.

  Confirms the body has an H1 title and that all seven required ``##`` sections
  are present and non-empty.

  Args:
    body: The markdown body that follows the frontmatter.

  Returns:
    A list of error strings describing every structural problem found; empty
    when the body conforms to the spec.
  """
  errors = []
  if not body.strip():
    return ["body is empty — it must contain the required sections"]

  heads = _heading_positions(body)

  # H1 title
  if not re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE):
    errors.append("missing H1 title line '# <Skill Name>'")

  # required sections present + non-empty
  sections = [
    (m.start(), m.group(1).strip())
    for m in re.finditer(r"^##\s+(.+?)\s*$", body, re.MULTILINE)
  ]
  present = {title.lower(): start for start, title in sections}
  required_lower = {s.lower(): s for s in REQUIRED_SECTIONS}

  for req in REQUIRED_SECTIONS:
    if req.lower() not in present:
      errors.append(f"missing required section '## {req}'")

  for start, title in sections:
    if title.lower() in required_lower and not _content_after(body, start, heads):
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
  with open(path, encoding="utf-8") as f:
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

  Returns:
    A sorted list of ``SKILL.md`` paths found under every root in
    :data:`SKILL_ROOTS`. Paths use forward slashes on every platform so that
    callers see identical strings on Linux, macOS, and Windows.
  """
  found = []
  for root in SKILL_ROOTS:
    matches = glob.glob(f"{root}/**/SKILL.md", recursive=True)
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
      res = subprocess.run(
        ["git", "diff", "--name-only", base],
        capture_output=True,
        text=True,
      )
  except FileNotFoundError:
    print("git not found on PATH; cannot compute changed skills.", file=sys.stderr)
    return []
  modules = set()
  for line in res.stdout.splitlines():
    manifest = _manifest_for(line)
    if manifest:
      modules.add(manifest)
  return sorted(m for m in modules if os.path.isfile(m))


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
  p = argparse.ArgumentParser(description="Validate SKILL.md files against the spec.")
  p.add_argument("paths", nargs="*", help="specific SKILL.md files to validate")
  p.add_argument("--all", action="store_true", help="validate every skill in the repo")
  p.add_argument(
    "--base", help="validate skills changed vs this git ref (e.g. origin/main)"
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

  failed = 0
  for t in targets:
    errs = validate_file(t)
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
