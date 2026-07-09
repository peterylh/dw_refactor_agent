# Shadow Run DAG Concurrency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DAG-aware concurrent job execution to shadow-run using the existing `--parallel` option.

**Architecture:** Extract single-job Phase 3 execution into a reusable function, then add a small scheduler that submits ready jobs while enforcing a global mysql invocation cap. Keep Phase 0-2 serial and preserve result JSON compatibility.

**Tech Stack:** Python 3.7-compatible standard library, existing `ThreadPoolExecutor`, existing `JobDAG`, existing `ExecutionPlanner`, pytest via project Makefile.

## Global Constraints

- `--parallel 1` must preserve current serial behavior.
- `--parallel` is the only concurrency knob and caps global mysql sessions across jobs and slice batches.
- No plan schema migration is required for the first implementation.
- Shadow-run must stop submitting new jobs after a failure.
- Use `make test` or targeted Make-compatible commands; do not run bare `pytest`.

---

### Task 1: Add Scheduler Regression Tests

**Files:**
- Modify: `tests/refact/test_shadow_run.py`

**Interfaces:**
- Consumes: `execute_shadow_plan(plan, parallel=N, batch_size=M)`
- Produces: Tests that define concurrent ready job behavior and failure propagation.

- [ ] **Step 1: Write failing tests**

Add tests that build small shadow plans with inline task SQL files:

```python
def test_execute_shadow_plan_runs_independent_jobs_concurrently(...):
    # dws_a and dws_b have no dependency; parallel=2 should overlap execution.

def test_execute_shadow_plan_waits_for_dependent_job(...):
    # dws_order must finish before ads_order starts.

def test_execute_shadow_plan_skips_downstream_after_upstream_failure(...):
    # dws_order fails; ads_order is not executed.
```

- [ ] **Step 2: Run tests to verify RED**

Run: `make test PYTEST_ARGS="tests/refact/test_shadow_run.py -k 'independent_jobs_concurrently or waits_for_dependent_job or skips_downstream_after_upstream_failure'"`

Expected: New tests fail because Phase 3 still executes jobs serially or lacks dependency-aware scheduling metadata.

### Task 2: Extract Single-Job Execution

**Files:**
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`

**Interfaces:**
- Produces: `_execute_shadow_job(job, *, root, planner, executor, qa_db, parallel, batch_size, timing_detail) -> tuple[dict, set[str]]`
- Consumes: existing `_job_result`, `_job_driver_values`, `_job_for_driver_value`, `_execute_invocation_batch`, `_job_batch_kwargs`

- [ ] **Step 1: Move current per-job logic into helper**

The helper returns the completed job result and the set of successfully recalculated job names.

- [ ] **Step 2: Keep serial path using helper**

`execute_shadow_plan(..., parallel=1)` should call the helper in `jobs_to_run` order.

- [ ] **Step 3: Run focused existing tests**

Run: `make test PYTEST_ARGS="tests/refact/test_shadow_run.py -k 'driver_values or missing_values or runs_slice_batches_in_parallel'"`

Expected: Existing behavior remains green.

### Task 3: Add DAG-Aware Global Scheduler

**Files:**
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`

**Interfaces:**
- Produces: `_run_shadow_jobs(...) -> dict`
- Produces: dependency helpers that compute in-degree/adjacency for `jobs_to_run`
- Consumes: `_execute_shadow_job(...)`

- [ ] **Step 1: Implement dependency loading**

Load the project lineage DAG artifact when available and compute dependencies for the `jobs_to_run` job names. If unavailable, construct a serial chain as fallback and record a warning.

- [ ] **Step 2: Implement global semaphore scheduling**

Use one `ThreadPoolExecutor(max_workers=parallel)` for ready jobs. Pass a shared semaphore with `parallel` permits into `_execute_shadow_job`; each invocation batch acquires one permit before calling mysql. This keeps total sessions bounded by `--parallel`.

- [ ] **Step 3: Preserve result order**

Store job results by original `jobs_to_run` index and emit JSON in plan order even if jobs finish out of order.

- [ ] **Step 4: Run RED tests to verify GREEN**

Run: `make test PYTEST_ARGS="tests/refact/test_shadow_run.py -k 'independent_jobs_concurrently or waits_for_dependent_job or skips_downstream_after_upstream_failure'"`

Expected: New tests pass.

### Task 4: Docs and CLI Help

**Files:**
- Modify: `src/dw_refactor_agent/refactor/run.py`
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`
- Modify: `docs/refactor_guides/common.md`

**Interfaces:**
- Consumes: existing `--parallel` parser option.
- Produces: updated help text and docs describing global DAG/job/slice concurrency.

- [ ] **Step 1: Update help text**

Change `--parallel` help from same-job slice wording to global shadow-run concurrency wording.

- [ ] **Step 2: Update guide**

Replace the old note that job-to-job concurrency is disabled.

### Task 5: Verification, Performance, Review

**Files:**
- Read-only review of modified files and tests.

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: verified test output, shop performance measurements, code review findings.

- [ ] **Step 1: Run focused tests**

Run: `make test PYTEST_ARGS="tests/refact/test_shadow_run.py tests/refact/test_run_cli.py tests/lineage/test_job_dag.py"`

- [ ] **Step 2: Run broader non-API tests if time allows**

Run: `make test`

- [ ] **Step 3: Measure shop performance**

Use the shop project with comparable `--parallel 1` and `--parallel 4` runs. Prefer real shadow-run if a valid manifest and database are available; otherwise use a controlled shop-derived dry-run or local mocked execution measurement and report the limitation.

- [ ] **Step 4: Request or perform code review**

Review for dependency correctness, failure propagation, result JSON compatibility, thread safety, and performance behavior.
