# DW Config Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the oversized root `config.py` module with a compact `config` package whose files map to clear configuration concepts.

**Architecture:** `config.core` owns repository constants, project definitions, and DB runtime settings. `config.assets` owns project asset paths and model metadata. `config.semantics` owns the business semantics catalog. `config.naming` owns the naming DSL parser, matcher, and diagnostics. `config.__init__` exposes the intentional public API.

**Tech Stack:** Python 3.7-compatible code, PyYAML, existing pytest/make test flow.

---

### Task 1: Package Skeleton and Naming DSL

**Files:**
- Create: `config/__init__.py`
- Create: `config/core.py`
- Create: `config/naming.py`
- Modify: `tests/test_naming_config.py`

- [x] Add `config.core` with `PROJECT_ROOT`, `TEXT_ENCODING`, `LAYER_ORDER`, `PROJECT_CONFIG`, `PROJECT_MAP`, `DB_ENV_CONFIG`, Doris defaults, and `get_mysql_cmd()`.
- [x] Move naming dataclasses and DSL helpers into `config.naming`.
- [x] Change naming tests to import from `config` / `config.naming`.
- [x] Add a malformed-template test for an unclosed `{` and implement `ValueError`.
- [x] Run `pytest -q tests/test_naming_config.py`.

### Task 2: Assets and Business Semantics

**Files:**
- Create: `config/assets.py`
- Create: `config/semantics.py`
- Modify: tests and application imports that read project paths, models, business semantics, and layer ordering.

- [x] Move project path helpers and model metadata loading to `config.assets`.
- [x] Move business semantics dataclasses and catalog loading to `config.semantics`.
- [x] Keep cache state private to those modules and expose explicit `clear_model_metadata_cache()`, `clear_business_semantics_cache()`, and `clear_naming_config_cache()` functions.
- [x] Update application code and tests to use the new modules.
- [x] Run focused config/path/model/semantics tests.

### Task 3: Remove Root Config Module and Verify

**Files:**
- Delete: `config.py`
- Modify: remaining imports in `assess/`, `lineage/`, `refact/`, `exec/`, `benchmarks/`, `tests/`.

- [x] Remove all production `import config` / `from config import ...` references.
- [x] Remove or update tests that directly touch old private cache names.
- [x] Run `rg "import config|from config import|config\\."` and handle remaining code references.
- [x] Run `make test`.
- [x] Review the final diff for conceptual boundaries, stale imports, and behavior risks.
