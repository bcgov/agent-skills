.PHONY: setup validate test format lint pack

# One-time (or after pulling new deps): install the Python tooling declared in
# pyproject.toml into a uv-managed virtualenv. Running `uv run` also does this
# lazily, but `make setup` is the explicit version that pre-warms the env.
setup:
	uv sync

# Validate every skill profile against the spec.
validate:
	uv run python scripts/validate_skill.py --all

# Run the validator unit tests.
test:
	uv run pytest -q

# Auto-format all Python to the repo style (2-space indent, double quotes).
format:
	uv run ruff format .

# Lint all Python: style, imports, docstrings, and bug-prone patterns.
lint:
	uv run ruff check .

# Dry-run the npm package for every publishable skill (CI does the real publish
# on merge). Only the root skills/ tree publishes; the .github/skills/ meta-skills
# are validated but never shipped, so they're excluded here.
pack:
	@for d in skills/*/; do \
		[ -f "$$d/package.json" ] || continue; \
		echo "== $$d =="; \
		( cd "$$d" && npm pack --dry-run ); \
	done
