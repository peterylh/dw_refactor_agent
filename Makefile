.PHONY: install-hooks env-create env-update doctor lint test test-cov benchmark-lineage benchmark-generate-llm

CONDA_ENV ?= dw-refactor-py37
CONDA_SUBDIR ?=
CONDA_SUBDIR_ARG = $(if $(CONDA_SUBDIR),--subdir $(CONDA_SUBDIR),)
CONDA_PACKAGES ?= python=3.7 pip pytest=7 pyyaml=6 requests pymysql typing_extensions
SQLGLOT_PACKAGE ?= sqlglot==26.9.0
RUFF_PACKAGE ?= ruff==0.12.0
PYTEST_COV_PACKAGES ?= pytest-cov==4.1.0 coverage[toml]==6.5.0
PYTHON ?= conda run -n $(CONDA_ENV) python
PYTEST_ARGS ?= -q -m "not api"
COVERAGE_ARGS ?= --cov=dw_refactor_agent --cov-report=term-missing --cov-report=xml
REQUIRED_PYTHON_VERSION ?= 3.7
REQUIRED_PYTHON_MODULES ?= yaml sqlglot pymysql pytest ruff
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
	PYTHONPATH=src $(PYTHON) -m ruff check .
	PYTHONPATH=src $(PYTHON) -m ruff format --check .

test: lint
	PYTHONPATH=src $(PYTHON) -m pytest $(PYTEST_ARGS)

test-cov: lint
	PYTHONPATH=src $(PYTHON) -m pytest $(PYTEST_ARGS) $(COVERAGE_ARGS)

benchmark-lineage: doctor
	PYTHONPATH=src $(PYTHON) benchmarks/lineage_extractor/run.py --size medium

benchmark-generate-llm: doctor
	PYTHONPATH=src $(PYTHON) benchmarks/table_inspector_layer/run.py --projects $(BENCHMARK_GENERATE_LLM_PROJECTS) --model $(BENCHMARK_GENERATE_LLM_MODEL) --base-url $(BENCHMARK_GENERATE_LLM_BASE_URL) --parallel $(BENCHMARK_GENERATE_LLM_PARALLEL) --max-retries $(BENCHMARK_GENERATE_LLM_MAX_RETRIES) --request-timeout $(BENCHMARK_GENERATE_LLM_REQUEST_TIMEOUT) --output $(BENCHMARK_GENERATE_LLM_OUTPUT)
