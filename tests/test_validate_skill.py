"""Unit tests for the SKILL.md validator.

Run with: python -m pytest tests/ -q

There is one test (or a focused cluster of tests) for every function in
``scripts/validate_skill.py`` — the frontmatter parsers, the body checks, the
filesystem/git discovery helpers, and the CLI entry point.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import validate_skill as v  # noqa: E402

VALID = """---
name: demo
description: A demo skill.
---

# Demo
One sentence summary.

## Use When
- something

## Don't Use When
- other → other-skill

## Workflow
1. do a thing

## Rules
- Always be careful

## Examples
- "do it" → does it

## Edge Cases
- If empty → fall back

## References
See [references/REFERENCE.md](references/REFERENCE.md)
"""


# --- Test helpers -----------------------------------------------------------


def _errors(text):
  """Run the full body + frontmatter validation pass over a SKILL.md string.

  Args:
    text: The complete contents of a SKILL.md file to validate.

  Returns:
    The combined list of frontmatter and body error strings (empty when the
    document is spec-compliant).
  """
  data, body, errs = v.parse_frontmatter(text)
  return errs + v.validate_frontmatter(data) + v.validate_body(body)


def _make_skill(root, name="demo"):
  """Write a valid SKILL.md into a fresh skill directory.

  Args:
    root: Directory in which to create the skill subdirectory.
    name: Name of the skill subdirectory to create.

  Returns:
    The path to the created skill directory.
  """
  skill_dir = os.path.join(root, name)
  os.makedirs(skill_dir, exist_ok=True)
  with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
    f.write(VALID)
  return skill_dir


# --- parse_frontmatter ------------------------------------------------------


def test_parse_frontmatter_missing():
  """Text without an opening fence is reported as missing frontmatter."""
  data, _, errs = v.parse_frontmatter("# no frontmatter")
  assert data is None
  assert any("frontmatter" in e for e in errs)


def test_parse_frontmatter_unclosed():
  """An opening fence with no closing fence is reported as not closed."""
  data, _, errs = v.parse_frontmatter("---\nname: x\n# body never closes")
  assert data is None
  assert any("not closed" in e for e in errs)


def test_parse_frontmatter_valid():
  """A well-formed document yields the mapping and the body after the fence."""
  data, body, errs = v.parse_frontmatter(VALID)
  assert errs == []
  assert data["name"] == "demo"
  assert body.lstrip().startswith("# Demo")


def test_parse_frontmatter_invalid_yaml():
  """A frontmatter block that is not valid YAML is reported."""
  data, _, errs = v.parse_frontmatter("---\nname: : :\n---\nbody")
  assert data is None
  assert any("YAML" in e for e in errs)


def test_parse_frontmatter_non_mapping():
  """A frontmatter block that is a list, not a mapping, is reported."""
  data, _, errs = v.parse_frontmatter("---\n- a\n- b\n---\nbody")
  assert data is None
  assert any("mapping" in e for e in errs)


# --- validate_frontmatter ---------------------------------------------------


def test_validate_frontmatter_none_is_empty():
  """A None mapping yields no errors (a parse error was already reported)."""
  assert v.validate_frontmatter(None) == []


def test_validate_frontmatter_missing_field():
  """A mapping missing a required field is reported by field name."""
  errs = v.validate_frontmatter({"name": "x"})
  assert any("description" in e for e in errs)


def test_validate_frontmatter_empty_value():
  """A required field present but blank is treated as missing."""
  errs = v.validate_frontmatter({"name": "   ", "description": "d"})
  assert any("name" in e for e in errs)


def test_validate_frontmatter_bad_name_format():
  """A name with uppercase or consecutive hyphens is reported as not kebab-case."""
  errs = v.validate_frontmatter({"name": "Bad--Name", "description": "d"})
  assert any("kebab-case" in e for e in errs)


def test_validate_frontmatter_name_too_long():
  """A name longer than the 64-char limit is reported."""
  errs = v.validate_frontmatter({"name": "a" * 65, "description": "d"})
  assert any("64-char" in e for e in errs)


def test_validate_frontmatter_description_too_long():
  """A description longer than the 1024-char limit is reported."""
  errs = v.validate_frontmatter({"name": "demo", "description": "x" * 1025})
  assert any("1024-char" in e for e in errs)


def test_validate_frontmatter_description_angle_brackets():
  """A description containing angle brackets is reported."""
  errs = v.validate_frontmatter({"name": "demo", "description": "use <here>"})
  assert any("angle brackets" in e for e in errs)


def test_validate_frontmatter_unexpected_key():
  """A frontmatter key outside the allowlist is reported."""
  errs = v.validate_frontmatter({"name": "demo", "description": "d", "bogus": 1})
  assert any("unexpected key" in e and "bogus" in e for e in errs)


def test_validate_frontmatter_allows_optional_keys():
  """The optional standard + repo keys pass without error."""
  errs = v.validate_frontmatter(
    {
      "name": "demo",
      "description": "d",
      "owner": "team",
      "tags": ["a"],
      "license": "Apache-2.0",
      "allowed-tools": "Read",
      "compatibility": "python3",
      "metadata": {"k": "v"},
    }
  )
  assert errs == []


# --- validate_name_matches_dir ----------------------------------------------


def test_name_matches_dir_ok():
  """A name equal to the directory basename passes."""
  assert v.validate_name_matches_dir({"name": "demo"}, "/x/skills/demo") == []


def test_name_matches_dir_mismatch():
  """A name that differs from the directory basename is reported."""
  errs = v.validate_name_matches_dir({"name": "demo"}, "/x/skills/other")
  assert any("must match the skill directory" in e for e in errs)


# --- validate_resource_layout -----------------------------------------------


def test_resource_layout_flat_ok():
  """Flat files under references/ pass with no error."""
  with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "references"))
    open(os.path.join(d, "references", "REFERENCE.md"), "w").close()
    assert v.validate_resource_layout(d) == []


def test_resource_layout_nested_reported():
  """A nested subdirectory under scripts/ is reported."""
  with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "scripts", "nested"))
    errs = v.validate_resource_layout(d)
    assert any("one level deep" in e for e in errs)


# --- _heading_positions -----------------------------------------------------


def test_heading_positions_finds_all_headings():
  """Every markdown heading offset is returned in document order."""
  body = "# A\ntext\n## B\nmore\n### C\n"
  pos = v._heading_positions(body)
  assert len(pos) == 3
  assert pos == sorted(pos)


# --- _content_after ---------------------------------------------------------


def test_content_after_returns_section_text():
  """The text between a heading and the next heading is returned, stripped."""
  body = "## A\nalpha\n## B\nbeta\n"
  heads = v._heading_positions(body)
  assert v._content_after(body, heads[0], heads) == "alpha"


def test_content_after_empty_section():
  """A heading immediately followed by another heading yields empty text."""
  body = "## A\n## B\nbeta\n"
  heads = v._heading_positions(body)
  assert v._content_after(body, heads[0], heads) == ""


# --- validate_body ----------------------------------------------------------


def test_validate_body_valid():
  """The body of a compliant document produces no errors."""
  _, body, _ = v.parse_frontmatter(VALID)
  assert v.validate_body(body) == []


def test_validate_body_empty():
  """An empty body is reported as missing the required sections."""
  assert any("empty" in e for e in v.validate_body("   "))


def test_validate_body_missing_h1():
  """A body with no H1 title line is reported."""
  errs = v.validate_body("## Use When\n- x\n")
  assert any("H1" in e for e in errs)


def test_valid_module_has_no_errors():
  """A fully spec-compliant SKILL.md produces no validation errors."""
  assert _errors(VALID) == []


# --- validate_length --------------------------------------------------------


def test_validate_length_within_limit():
  """A SKILL.md at or under the line cap produces no error."""
  text = "\n".join(["x"] * v.MAX_SKILL_LINES)
  assert v.validate_length(text) == []


def test_validate_length_over_limit():
  """A SKILL.md past the line cap is reported, pointing at references/."""
  text = "\n".join(["x"] * (v.MAX_SKILL_LINES + 1))
  errs = v.validate_length(text)
  assert any("exceeds" in e and "references/" in e for e in errs)


def test_missing_required_section():
  """Omitting a required ## section is reported by section name."""
  text = VALID.replace("## Edge Cases\n- If empty → fall back\n\n", "")
  errs = _errors(text)
  assert any("Edge Cases" in e for e in errs)


def test_empty_required_section():
  """A required ## section with no content is reported as empty."""
  text = VALID.replace("## Rules\n- Always be careful", "## Rules\n")
  errs = _errors(text)
  assert any("Rules" in e and "empty" in e for e in errs)


def test_h1_without_summary_is_valid():
  """An H1 title with no summary line beneath it is accepted (summary dropped)."""
  text = VALID.replace("# Demo\nOne sentence summary.", "# Demo")
  assert _errors(text) == []


def test_missing_name_and_description():
  """Both required frontmatter fields are reported when each is absent."""
  # Keep the frontmatter block closed (swap the keys out) so we exercise the
  # per-field check rather than the "block not closed" path.
  text = VALID.replace("name: demo", "owner: nobody").replace(
    "description: A demo skill.", "tags: [example]"
  )
  errs = _errors(text)
  assert any("name" in e for e in errs)
  assert any("description" in e for e in errs)


# --- validate_file ----------------------------------------------------------


def test_validate_file_not_found():
  """A path that does not exist is reported as not found."""
  assert any("not found" in e for e in v.validate_file("/no/such/SKILL.md"))


def test_validate_file_valid_skill():
  """A complete skill directory validates with no errors end to end."""
  with tempfile.TemporaryDirectory() as root:
    skill_dir = _make_skill(root)
    assert v.validate_file(os.path.join(skill_dir, "SKILL.md")) == []


# --- discover_all -----------------------------------------------------------


def test_discover_all_finds_manifests_under_both_roots():
  """SKILL.md files under both skills/ and .github/skills/ are discovered."""
  with tempfile.TemporaryDirectory() as root:
    os.makedirs(os.path.join(root, "skills", "demo"))
    open(os.path.join(root, "skills", "demo", "SKILL.md"), "w").close()
    os.makedirs(os.path.join(root, ".github", "skills", "meta"))
    open(os.path.join(root, ".github", "skills", "meta", "SKILL.md"), "w").close()
    cwd = os.getcwd()
    try:
      os.chdir(root)
      found = v.discover_all()
    finally:
      os.chdir(cwd)
    # Paths are normalized to forward slashes on every platform.
    assert found == [
      ".github/skills/meta/SKILL.md",
      "skills/demo/SKILL.md",
    ]


# --- changed_modules --------------------------------------------------------


def test_changed_modules_maps_changed_files_to_manifests():
  """Changed files under either root map to their manifest; others are ignored."""

  class _FakeProc:
    returncode = 0
    stdout = (
      "skills/demo/SKILL.md\n"
      ".github/skills/meta/SKILL.md\n"
      "README.md\n"
      "scripts/validate_skill.py\n"
    )

  with tempfile.TemporaryDirectory() as root:
    os.makedirs(os.path.join(root, "skills", "demo"))
    open(os.path.join(root, "skills", "demo", "SKILL.md"), "w").close()
    os.makedirs(os.path.join(root, ".github", "skills", "meta"))
    open(os.path.join(root, ".github", "skills", "meta", "SKILL.md"), "w").close()
    orig_run = v.subprocess.run
    cwd = os.getcwd()
    try:
      v.subprocess.run = lambda *a, **k: _FakeProc()
      os.chdir(root)
      mods = v.changed_modules("origin/main")
    finally:
      os.chdir(cwd)
      v.subprocess.run = orig_run
    # Manifest paths use forward slashes on every platform.
    assert mods == [
      ".github/skills/meta/SKILL.md",
      "skills/demo/SKILL.md",
    ]


def test_changed_modules_returns_empty_when_git_missing():
  """A host without git produces a clean empty result instead of a stack trace."""

  def _raise(*_a, **_k):
    raise FileNotFoundError("git")

  orig_run = v.subprocess.run
  try:
    v.subprocess.run = _raise
    assert v.changed_modules("origin/main") == []
  finally:
    v.subprocess.run = orig_run


# --- main -------------------------------------------------------------------


def test_main_no_targets_returns_zero():
  """With no skills selected, the CLI is a no-op that succeeds."""
  assert v.main([]) == 0


def test_main_valid_path_returns_zero():
  """A valid skill passed by path makes the CLI exit 0."""
  with tempfile.TemporaryDirectory() as root:
    skill_dir = _make_skill(root)
    assert v.main([os.path.join(skill_dir, "SKILL.md")]) == 0


def test_main_invalid_path_returns_one():
  """A non-compliant skill makes the CLI exit 1."""
  with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
      f.write("no frontmatter at all")
    assert v.main([path]) == 1


# --- Duplicate-detection helpers --------------------------------------------


def _write_skill_for_dup(root, name, *, desc="A demo skill.", body_suffix=""):
  """Write a complete SKILL.md under ``root/<name>/`` for duplicate-detection tests.

  The body is identical across calls except for the H1 line, the summary
  line, and any caller-supplied ``body_suffix`` appended after the standard
  ``## References`` section. That lets a single helper drive each scenario
  (same name, same description, same body, all distinct) by varying just
  the inputs that matter for the test.
  """
  skill_dir = os.path.join(root, name)
  os.makedirs(skill_dir, exist_ok=True)
  text = (
    f"---\nname: {name}\ndescription: {desc}\n---\n\n"
    f"# {name}\nSummary for {name}.\n\n"
    "## Use When\n- something\n\n"
    "## Don't Use When\n- other → other-skill\n\n"
    "## Workflow\n1. do a thing\n\n"
    "## Rules\n- Always be careful\n\n"
    '## Examples\n- "do it" → does it\n\n'
    "## Edge Cases\n- If empty → fall back\n\n"
    "## References\nSee REFERENCE.md\n"
    f"{body_suffix}"
  )
  path = os.path.join(skill_dir, "SKILL.md")
  with open(path, "w", encoding="utf-8") as f:
    f.write(text)
  return path


# --- _normalize_text / _body_fingerprint ------------------------------------


def test_normalize_text_lowercases_and_collapses_whitespace():
  """Mixed-case input with runs of whitespace collapses to a single comparable form."""
  assert v._normalize_text("  Hello  WORLD\n\t") == "hello world"


def test_normalize_text_empty_string():
  """Empty input returns an empty fingerprint instead of raising."""
  assert v._normalize_text("") == ""


def test_body_fingerprint_drops_h1_and_summary_preamble():
  """Everything before the first '## ' heading is dropped from the fingerprint."""
  body = "# Title\nSummary line.\n\n## Use When\n- thing\n"
  fp = v._body_fingerprint(body)
  assert fp.startswith("## use when")
  assert "title" not in fp
  assert "summary" not in fp


def test_body_fingerprint_without_h2_keeps_full_body():
  """When there is no '## ' heading the regex finds nothing and the body is kept."""
  body = "# Only an H1\nSome text.\n"
  fp = v._body_fingerprint(body)
  assert "only an h1" in fp
  assert "some text" in fp


# --- check_duplicates -------------------------------------------------------


def test_check_duplicates_distinct_skills_pass():
  """Two skills with distinct names, descriptions, and bodies produce no errors."""
  with tempfile.TemporaryDirectory() as root:
    a = _write_skill_for_dup(root, "alpha", desc="Alpha skill.")
    b = _write_skill_for_dup(
      root, "beta", desc="Beta skill.", body_suffix="\nExtra beta-only line.\n"
    )
    assert v.check_duplicates([a, b]) == {}


def test_check_duplicates_same_description_flagged():
  """A description copied verbatim from another skill is flagged on both sides."""
  with tempfile.TemporaryDirectory() as root:
    a = _write_skill_for_dup(root, "alpha", desc="Shared description text.")
    b = _write_skill_for_dup(
      root,
      "beta",
      desc="Shared description text.",
      body_suffix="\nExtra beta-only line.\n",
    )
    errs = v.check_duplicates([a, b])
    assert any("description" in e for e in errs[a])
    assert any("description" in e for e in errs[b])


def test_check_duplicates_same_body_with_different_h1_flagged():
  """A body matching another skill's ``##`` sections is flagged when only H1 differs."""
  with tempfile.TemporaryDirectory() as root:
    a = _write_skill_for_dup(root, "alpha", desc="Alpha skill.")
    b = _write_skill_for_dup(root, "beta", desc="Beta skill.")
    errs = v.check_duplicates([a, b])
    assert any("body content" in e for e in errs[a])
    assert any("body content" in e for e in errs[b])


def test_check_duplicates_same_name_in_different_dirs_flagged():
  """Two skills that declare the same frontmatter ``name`` are flagged."""
  with tempfile.TemporaryDirectory() as root:
    base = (
      "---\nname: shared\ndescription: {desc}\n---\n\n"
      "# {h1}\nSummary.\n\n"
      "## Use When\n- {body}\n\n"
      "## Don't Use When\n- x\n\n## Workflow\n1. y\n\n"
      "## Rules\n- z\n\n## Examples\n- q\n\n"
      "## Edge Cases\n- w\n\n## References\n- r\n"
    )
    a_dir = os.path.join(root, "a-tree", "shared")
    b_dir = os.path.join(root, "b-tree", "shared")
    os.makedirs(a_dir)
    os.makedirs(b_dir)
    a = os.path.join(a_dir, "SKILL.md")
    b = os.path.join(b_dir, "SKILL.md")
    with open(a, "w", encoding="utf-8") as f:
      f.write(base.format(desc="One.", h1="A", body="alpha-thing"))
    with open(b, "w", encoding="utf-8") as f:
      f.write(base.format(desc="Two.", h1="B", body="beta-thing"))
    errs = v.check_duplicates([a, b])
    assert any("name" in e for e in errs[a])
    assert any("name" in e for e in errs[b])


def test_check_duplicates_target_compared_against_corpus():
  """A target is flagged when it duplicates a corpus skill not in the target list."""
  with tempfile.TemporaryDirectory() as root:
    a = _write_skill_for_dup(root, "alpha", desc="Same.")
    b = _write_skill_for_dup(root, "beta", desc="Same.")
    errs = v.check_duplicates([b], corpus=[a, b])
    assert b in errs
    assert any("alpha" in e for e in errs[b])
    assert a not in errs  # alpha was not a target, so it gets no entry


def test_check_duplicates_ignores_missing_files():
  """A path that does not exist on disk is silently skipped, not raised on."""
  assert v.check_duplicates(["/no/such/SKILL.md"]) == {}


def test_check_duplicates_skips_empty_fingerprints():
  """Skills with no parseable frontmatter do not match each other via empty strings."""
  with tempfile.TemporaryDirectory() as root:
    a_dir = os.path.join(root, "alpha")
    b_dir = os.path.join(root, "beta")
    os.makedirs(a_dir)
    os.makedirs(b_dir)
    a = os.path.join(a_dir, "SKILL.md")
    b = os.path.join(b_dir, "SKILL.md")
    with open(a, "w", encoding="utf-8") as f:
      f.write("alpha body only, no frontmatter")
    with open(b, "w", encoding="utf-8") as f:
      f.write("beta body only, no frontmatter")
    assert v.check_duplicates([a, b]) == {}


# --- main with duplicate detection ------------------------------------------


def test_main_flags_cross_skill_duplicates():
  """`main` exits 1 when a target duplicates another skill discovered in the repo."""
  with tempfile.TemporaryDirectory() as root:
    skills = os.path.join(root, "skills")
    os.makedirs(skills)
    _write_skill_for_dup(skills, "alpha", desc="Shared description.")
    b = _write_skill_for_dup(skills, "beta", desc="Shared description.")
    cwd = os.getcwd()
    try:
      os.chdir(root)
      rc = v.main([os.path.relpath(b, root)])
    finally:
      os.chdir(cwd)
    assert rc == 1


def test_main_no_duplicates_flag_skips_dup_check():
  """`--no-duplicates` lets otherwise-duplicate skills pass."""
  with tempfile.TemporaryDirectory() as root:
    skills = os.path.join(root, "skills")
    os.makedirs(skills)
    _write_skill_for_dup(skills, "alpha", desc="Shared description.")
    b = _write_skill_for_dup(skills, "beta", desc="Shared description.")
    cwd = os.getcwd()
    try:
      os.chdir(root)
      rc = v.main(["--no-duplicates", os.path.relpath(b, root)])
    finally:
      os.chdir(cwd)
    assert rc == 0
