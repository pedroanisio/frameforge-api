UV ?= uv

.PHONY: help sync test schema schema-check doc-check goldens lint check build clean

help:  ## show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

sync:  ## install the dev environment
	$(UV) sync --all-groups

test:  ## run the contract + extraction-fidelity suites
	$(UV) run pytest

schema:  ## regenerate the committed JSON schema from the models
	$(UV) run ff-schema

schema-check:  ## GATE: fail if the committed schema drifted from the models
	$(UV) run ff-schema --check

doc-check:  ## GATE: fail if the docs drifted from the code
	$(UV) run python tooling/check_docs.py

goldens:  ## rewrite tests/golden/ — ONLY when the contract is meant to move
	$(UV) run python tests/regen_goldens.py

lint:  ## ruff
	$(UV) run ruff check src tests tooling

check: schema-check doc-check lint test  ## every local gate

build:  ## build the wheel + sdist
	$(UV) build

clean:
	rm -rf dist build .pytest_cache .ruff_cache htmlcov .coverage
