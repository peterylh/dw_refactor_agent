# External Baseline DDL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store baseline DDL in standalone SQL files referenced and integrity-checked by `verification/plan.json`.

**Architecture:** Keep baseline selection in `verification_plan.py`, but move artifact serialization and loading into a focused `plan_artifact.py` module. The writer externalizes transient DDL text into SQL files and emits references; the loader validates those references and materializes DDL before existing shadow-manifest and shadow-run code executes.

**Tech Stack:** Python 3.7, pathlib, hashlib, JSON, pytest, Doris SQL text.

## Global Constraints

- Only `baseline_ddl_refs` is supported in persisted plans; embedded `baseline_ddl` is rejected.
- Reference paths are relative to `plan.json`, cannot escape its directory, and include SHA-256 of exact UTF-8 file bytes.
- DDL files preserve the exact text supplied by the planner; no formatter or AST regeneration is applied.
- Tests run through the configured `dw-refactor-py37` conda environment, never bare `pytest`.

---

### Task 1: Plan artifact writer and standalone DDL files

**Files:**
- Create: `src/dw_refactor_agent/refactor/plan_artifact.py`
- Create: `tests/refact/test_plan_artifact.py`

**Interfaces:**
- Produces: `write_verification_plan(plan_path: Path, plan: dict) -> dict`

- [ ] **Step 1: Write failing writer tests**

Cover exact source preservation, exact hashes, no embedded field, stale-file cleanup, and safe filenames.

- [ ] **Step 2: Run tests and verify RED**

Run: `make test PYTEST_ARGS='tests/refact/test_plan_artifact.py -q'`

Expected: collection/import failure because `plan_artifact` does not exist.

- [ ] **Step 3: Implement the minimal source-preserving writer**

The writer consumes transient `plan["baseline_ddl"]`, writes its text unchanged
to `baseline_ddl/<table>.sql`, computes SHA-256, returns/writes a copy containing
`baseline_ddl_refs`, and removes unreferenced `.sql` files.

- [ ] **Step 4: Run focused writer tests and verify GREEN**

Run: `make test PYTEST_ARGS='tests/refact/test_plan_artifact.py -q'`

Expected: all tests pass.

### Task 2: Strict plan loader

**Files:**
- Modify: `src/dw_refactor_agent/refactor/plan_artifact.py`
- Modify: `tests/refact/test_plan_artifact.py`

**Interfaces:**
- Produces: `load_verification_plan(plan_path: Path) -> dict`
- Returns an executable plan with internal `baseline_ddl: dict[str, str]`.

- [ ] **Step 1: Write failing loader tests**

Cover successful materialization, empty refs, embedded legacy field rejection,
missing/malformed references, absolute/traversal paths, missing files, and hash
mismatch.

- [ ] **Step 2: Run loader tests and verify RED**

Run: `make test PYTEST_ARGS='tests/refact/test_plan_artifact.py -q'`

Expected: failures because `load_verification_plan` is absent.

- [ ] **Step 3: Implement strict reference validation and materialization**

Resolve files beneath the plan directory, verify exact bytes before decoding,
and raise a plan-artifact-specific `ValueError` with table/path context.

- [ ] **Step 4: Run artifact tests and verify GREEN**

Run: `make test PYTEST_ARGS='tests/refact/test_plan_artifact.py -q'`

Expected: all tests pass.

### Task 3: Integrate writer and loader into refactor CLI

**Files:**
- Modify: `src/dw_refactor_agent/refactor/run.py`
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`
- Modify: `src/dw_refactor_agent/refactor/compare.py`
- Modify: `tests/refact/test_run_cli.py`
- Modify: `tests/refact/test_shadow_run.py`
- Modify: `tests/refact/test_compare.py`

**Interfaces:**
- `analyze` calls `write_verification_plan` instead of generic JSON writing.
- `run_shadow_plan` and `compare_shadow_results` call
  `load_verification_plan` before their existing internal execution functions.

- [ ] **Step 1: Write failing CLI/consumer integration tests**

Assert analyze writes refs and SQL files, shadow-run consumes referenced plans,
compare consumes referenced plans, and invalid references fail before database
operations.

- [ ] **Step 2: Run affected tests and verify RED**

Run: `make test PYTEST_ARGS='tests/refact/test_run_cli.py tests/refact/test_shadow_run.py tests/refact/test_compare.py -q'`

Expected: new reference-format assertions fail.

- [ ] **Step 3: Replace generic plan serialization and direct JSON loading**

Keep `execute_shadow_plan(plan)` and `run_checks(plan)` operating on
materialized in-memory plans; change only file-backed boundaries.

- [ ] **Step 4: Run affected tests and verify GREEN**

Run: `make test PYTEST_ARGS='tests/refact/test_run_cli.py tests/refact/test_shadow_run.py tests/refact/test_compare.py -q'`

Expected: all affected tests pass.

### Task 4: Update schema expectations and documentation

**Files:**
- Modify: `tests/refact/test_verification_plan.py`
- Modify: `tests/refact/test_shadow_manifest.py`
- Modify: `src/dw_refactor_agent/refactor/AGENTS.md`
- Modify: `docs/superpowers/specs/2026-07-11-external-baseline-ddl-design.md` only if implementation reveals a necessary clarification.

**Interfaces:**
- Planner unit tests may continue to assert transient `baseline_ddl` because
  externalization is an artifact-boundary responsibility.
- Persisted-plan tests assert only `baseline_ddl_refs`.

- [ ] **Step 1: Update documentation and persisted-schema assertions**

Document the new directory, reference fields, strict old-run boundary, and
hash validation behavior.

- [ ] **Step 2: Run the complete refactor test group**

Run: `make test PYTEST_ARGS='tests/refact -q'`

Expected: all refactor tests pass.

### Task 5: Verification and Code Review

**Files:**
- Review all changed files.

**Interfaces:**
- No new interfaces.

- [ ] **Step 1: Run static checks and full non-API tests**

Run: `make doctor`, `make test`.

Expected: configured Python 3.7 environment is healthy and all non-API tests pass.

- [ ] **Step 2: Run artifact smoke inspection**

Generate a representative plan in tests or a temporary directory and inspect
that `plan.json` is compact, referenced SQL matches its source, and its digest
matches.

- [ ] **Step 3: Perform Code Review**

Review correctness, failure ordering, path traversal resistance, source
fidelity, stale cleanup, Python 3.7 compatibility, and unintended behavior
changes. Fix findings using new RED/GREEN tests, then rerun affected and full
verification.

- [ ] **Step 4: Report final diff and verification evidence**

Include changed files, artifact schema, tests executed, review findings, and
remaining limitations.
