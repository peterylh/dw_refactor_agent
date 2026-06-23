.PHONY: install-hooks env-create env-update doctor lint test test-cov

CONDA_ENV ?= dw-refactor-py37
CONDA_SUBDIR ?=
CONDA_SUBDIR_ARG = $(if $(CONDA_SUBDIR),--subdir $(CONDA_SUBDIR),)
CONDA_PACKAGES ?= python=3.7 pip pytest=7 pyyaml=6 requests pymysql typing_extensions
SQLGLOT_PACKAGE ?= sqlglot==26.9.0
RUFF_PACKAGE ?= ruff==0.12.0
PYTEST_COV_PACKAGES ?= pytest-cov==4.1.0 coverage[toml]==6.5.0
PYTHON ?= conda run -n $(CONDA_ENV) python
PYTEST_ARGS ?= -q -m "not api"
COVERAGE_ARGS ?= --cov=config --cov=lineage --cov=assess --cov=ddl_deriver --cov=refact --cov=exec --cov-report=term-missing --cov-report=xml
REQUIRED_PYTHON_VERSION ?= 3.7
REQUIRED_PYTHON_MODULES ?= yaml sqlglot pymysql pytest ruff

-include Makefile.local

install-hooks:
	git config core.hooksPath .githooks

env-create:
	conda create -y -n $(CONDA_ENV) $(CONDA_SUBDIR_ARG) --override-channels --channel conda-forge $(CONDA_PACKAGES)
	conda run -n $(CONDA_ENV) python -m pip install --no-cache-dir $(SQLGLOT_PACKAGE)
	conda run -n $(CONDA_ENV) python -m pip install --no-cache-dir $(RUFF_PACKAGE)
	conda run -n $(CONDA_ENV) python -m pip install --no-cache-dir $(PYTEST_COV_PACKAGES)

env-update:
	conda install -y -n $(CONDA_ENV) --override-channels --channel conda-forge $(CONDA_PACKAGES)
	conda run -n $(CONDA_ENV) python -m pip install --upgrade --no-cache-dir $(SQLGLOT_PACKAGE)
	conda run -n $(CONDA_ENV) python -m pip install --upgrade --no-cache-dir $(RUFF_PACKAGE)
	conda run -n $(CONDA_ENV) python -m pip install --upgrade --no-cache-dir $(PYTEST_COV_PACKAGES)

doctor:
	@$(PYTHON) -c "import importlib.util, sys; expected=tuple(map(int, '$(REQUIRED_PYTHON_VERSION)'.split('.'))); missing=[m for m in '$(REQUIRED_PYTHON_MODULES)'.split() if importlib.util.find_spec(m) is None]; print('python:', sys.executable); print('version:', sys.version.split()[0]); print('expected:', '$(REQUIRED_PYTHON_VERSION)'); print('modules:', 'ok' if not missing else 'missing ' + ', '.join(missing)); raise SystemExit(0 if sys.version_info[:2] == expected and not missing else 1)"

lint: doctor
	PYTHONPATH= $(PYTHON) -m ruff check .
	PYTHONPATH= $(PYTHON) -m ruff format --check .

test: lint
	PYTHONPATH= $(PYTHON) -m pytest $(PYTEST_ARGS)

test-cov: lint
	PYTHONPATH= $(PYTHON) -m pytest $(PYTEST_ARGS) $(COVERAGE_ARGS)
