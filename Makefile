.PHONY: install-hooks lint test

PYTHON ?= python
PYTEST_ARGS ?= -q -m "not api"
RUFF ?= ruff

install-hooks:
	git config core.hooksPath .githooks

lint:
	$(RUFF) check .
	$(RUFF) format --check .

test: lint
	PYTHONPATH=. $(PYTHON) -m pytest $(PYTEST_ARGS)
