.PHONY: setup validate validate-one test format lint

# One-time (or after pulling new deps): install the Python tooling declared in
# pyproject.toml into a uv-managed virtualenv. Running `uv run` also does this
# lazily, but `make setup` is the explicit version that pre-warms the env.
setup:
	uv sync

# Validate every skill profile against the spec.
validate:
	uv run python scripts/validate_skill.py --all

# Validate a single skill profile. Usage: make validate-one SKILL=skills/azure-networking/SKILL.md
validate-one:
	@test -n "$(SKILL)" || (echo 'Usage: make validate-one SKILL=skills/<name>/SKILL.md' >&2; exit 2)
	uv run python scripts/validate_skill.py $(SKILL)

# Run the validator unit tests.
test:
	uv run pytest -q

# Auto-format all Python to the repo style (2-space indent, double quotes).
format:
	uv run ruff format .

# Lint all Python: style, imports, docstrings, and bug-prone patterns. Also
# lints the GitHub Actions workflow YAML (2-space indent enforced; see
# .yamllint at the repo root).
lint:
	uv run ruff check .
	uv run yamllint .github/workflows
