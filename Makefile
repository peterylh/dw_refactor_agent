.PHONY: install-hooks env-create env-update doctor lint lint-duplicates test test-cov benchmark-lineage benchmark-generate-llm

CONDA ?= conda
CONDA_ENV ?= dw-refactor-py37
CONDA_SUBDIR ?=
CONDA_SUBDIR_ARG = $(if $(CONDA_SUBDIR),--subdir $(CONDA_SUBDIR),)
CONDA_PACKAGES ?= python=3.7 pip pytest=7 pyyaml=6 requests pymysql typing_extensions
SQLGLOT_PACKAGE ?= git+https://github.com/HYDCP/hy-sqlglot.git@77fe22e66498ea4ad996d9c5a172c69d7ac693c8
RUFF_PACKAGE ?= ruff==0.12.0
PYLINT_PACKAGE ?= pylint==2.17.7
PYTEST_COV_PACKAGES ?= pytest-cov==4.1.0 coverage[toml]==6.5.0
CONDA_PYTHON = $(CONDA) run -n $(CONDA_ENV) /bin/sh -c 'exec "$$CONDA_PREFIX/bin/python" "$$@"' conda-python
PYTHON ?= $(CONDA_PYTHON)
PYTEST_ARGS ?= -q -m "not api"
COVERAGE_ARGS ?= --cov=dw_refactor_agent --cov-report=term-missing --cov-report=xml
REQUIRED_PYTHON_VERSION ?= 3.7
REQUIRED_PYTHON_MODULES ?= yaml sqlglot pymysql pytest ruff pylint
EXPECTED_CONDA_ENV ?= $(CONDA_ENV)
DUPLICATE_PATHS ?= src tests scripts benchmarks warehouses
DUPLICATE_MIN_LINES ?= 8
BENCHMARK_GENERATE_LLM_PROJECTS ?= shop finance_analytics
BENCHMARK_GENERATE_LLM_MODEL ?= deepseek-v4-pro
BENCHMARK_GENERATE_LLM_BASE_URL ?= https://api.deepseek.com
BENCHMARK_GENERATE_LLM_PARALLEL ?= 4
BENCHMARK_GENERATE_LLM_MAX_RETRIES ?= 1
BENCHMARK_GENERATE_LLM_REQUEST_TIMEOUT ?= 240
BENCHMARK_GENERATE_LLM_OUTPUT ?= /tmp/generate_llm_cold_start_benchmark.json

-include Makefile.local

install-hooks:
	git config core.hooksPath .githooks

env-create:
	$(CONDA) create -y -n $(CONDA_ENV) $(CONDA_SUBDIR_ARG) --override-channels --channel conda-forge $(CONDA_PACKAGES)
	$(CONDA_PYTHON) -m pip install --no-cache-dir $(SQLGLOT_PACKAGE)
	$(CONDA_PYTHON) -m pip install --no-cache-dir $(RUFF_PACKAGE)
	$(CONDA_PYTHON) -m pip install --no-cache-dir $(PYLINT_PACKAGE)
	$(CONDA_PYTHON) -m pip install --no-cache-dir $(PYTEST_COV_PACKAGES)

env-update:
	$(CONDA) install -y -n $(CONDA_ENV) --override-channels --channel conda-forge $(CONDA_PACKAGES)
	$(CONDA_PYTHON) -m pip install --upgrade --no-cache-dir $(SQLGLOT_PACKAGE)
	$(CONDA_PYTHON) -m pip install --upgrade --no-cache-dir $(RUFF_PACKAGE)
	$(CONDA_PYTHON) -m pip install --upgrade --no-cache-dir $(PYLINT_PACKAGE)
	$(CONDA_PYTHON) -m pip install --upgrade --no-cache-dir $(PYTEST_COV_PACKAGES)

doctor:
	@REQUIRED_PYTHON_VERSION="$(REQUIRED_PYTHON_VERSION)" REQUIRED_PYTHON_MODULES="$(REQUIRED_PYTHON_MODULES)" EXPECTED_CONDA_ENV="$(EXPECTED_CONDA_ENV)" $(PYTHON) scripts/python_env_doctor.py

lint: doctor
	PYTHONPATH=src $(PYTHON) -m ruff check .
	PYTHONPATH=src $(PYTHON) -m ruff format --check .

lint-duplicates: doctor
	PYTHONPATH=src $(PYTHON) scripts/check_duplicates.py --min-lines $(DUPLICATE_MIN_LINES) $(DUPLICATE_PATHS)

test: lint
	PYTHONPATH=src $(PYTHON) -m pytest $(PYTEST_ARGS)

test-cov: lint
	PYTHONPATH=src $(PYTHON) -m pytest $(PYTEST_ARGS) $(COVERAGE_ARGS)

benchmark-lineage: doctor
	PYTHONPATH=src $(PYTHON) benchmarks/lineage_extractor/run.py --size medium

benchmark-generate-llm: doctor
	PYTHONPATH=src $(PYTHON) benchmarks/table_inspector_layer/run.py --projects $(BENCHMARK_GENERATE_LLM_PROJECTS) --model $(BENCHMARK_GENERATE_LLM_MODEL) --base-url $(BENCHMARK_GENERATE_LLM_BASE_URL) --parallel $(BENCHMARK_GENERATE_LLM_PARALLEL) --max-retries $(BENCHMARK_GENERATE_LLM_MAX_RETRIES) --request-timeout $(BENCHMARK_GENERATE_LLM_REQUEST_TIMEOUT) --output $(BENCHMARK_GENERATE_LLM_OUTPUT)
