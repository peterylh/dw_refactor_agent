# Refactor Plan Job Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed run-local lineage-derived job dependencies in every verification plan and make shadow-run consume that graph exclusively.

**Architecture:** `build_verification_plan()` builds one in-memory `JobDAG`, uses it for ordering and for the final induced dependency map, and writes the map into the plan. Shadow-run validates that map before any work and schedules from the validated graph without loading project artifacts or falling back to serial order.

**Tech Stack:** Python 3.7-compatible code, existing `JobDAG`, JSON plan artifacts, pytest through the project Makefile.

## Global Constraints

- Do not read project-level `job_dag.json` from analyze or shadow-run.
- Do not support verification plans that omit `job_dependencies`.
- Preserve case-insensitive DAG matching and user-visible job name casing.
- Keep `jobs_to_run` as execution descriptor objects.
- Run tests through `make test`; do not invoke bare pytest.

---

### Task 1: Generate Plan Dependencies From Current Lineage

**Files:**
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`
- Test: `tests/refact/test_verification_plan.py`

**Interfaces:**
- Consumes: `asset_job_dag_from_lineage(lineage_data) -> JobDAG`
- Produces: `_build_job_execution_graph(jobs, lineage_data) -> tuple[list[str], dict[str, list[str]]]`
- Produces: `plan["job_dependencies"]`

- [ ] **Step 1: Write a failing multi-job plan test**

Create three full-materialization demo tasks and lineage edges `dwd -> dws -> ads`. Assert that `jobs_to_run` is topologically ordered and that the plan contains:

```python
assert plan["job_dependencies"] == {
    "ads_order": ["dws_order"],
    "dwd_order": [],
    "dws_order": ["dwd_order"],
}
```

Wrap `asset_job_dag_from_lineage` and assert it is called once.

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
make test PYTEST_ARGS="tests/refact/test_verification_plan.py -k 'writes_job_dependencies' -q"
```

Expected: FAIL because `job_dependencies` is absent.

- [ ] **Step 3: Implement one-pass graph planning**

Replace the sort-only helper with a helper that creates one DAG, topologically
sorts the final executable job set, computes its adjacency, inverts adjacency
to downstream-to-upstream lists, and sorts keys and values deterministically.
Add the result to the plan return object.

- [ ] **Step 4: Run verification plan tests**

Run:

```bash
make test PYTEST_ARGS="tests/refact/test_verification_plan.py -q"
```

Expected: PASS.

### Task 2: Make Shadow-Run Strictly Plan-Driven

**Files:**
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`
- Test: `tests/refact/test_shadow_run.py`

**Interfaces:**
- Produces: `_job_dependencies_from_plan(plan) -> tuple[dict[str, int], dict[str, list[str]]]`
- Consumes: complete `plan["job_dependencies"]`

- [ ] **Step 1: Write failing strict-validation tests**

Add tests that assert missing dependencies, incomplete keys, unknown upstreams,
self-dependencies, duplicate dependencies, and cycles raise `ValueError` before
`run_sql` is called. Update scheduler tests to embed dependencies instead of
writing project DAG artifacts.

- [ ] **Step 2: Run the focused tests to verify RED**

Run:

```bash
make test PYTEST_ARGS="tests/refact/test_shadow_run.py -k 'job_dependencies or independent_jobs_concurrently or uses_dag_order or skips_downstream' -q"
```

Expected: FAIL because shadow-run still loads or falls back to project DAG.

- [ ] **Step 3: Implement strict dependency validation**

Remove project DAG imports and path loading. Validate the plan graph before
dry-run or database work, detect cycles with Kahn traversal, pass validated
in-degree and adjacency into the Phase 3 scheduler, and report
`scheduler: "plan"`.

- [ ] **Step 4: Run shadow-run tests**

Run:

```bash
make test PYTEST_ARGS="tests/refact/test_shadow_run.py tests/refact/test_run_cli.py -q"
```

Expected: PASS.

### Task 3: Real Shop Validation And Review

**Files:**
- Review: `src/dw_refactor_agent/refactor/verification_plan.py`
- Review: `src/dw_refactor_agent/refactor/shadow_run.py`
- Review: relevant tests and generated shop artifacts

**Interfaces:**
- Consumes: shop current lineage and task assets
- Produces: evidence that plan scheduling works without `job_dag.json`

- [ ] **Step 1: Run focused and full tests**

Run:

```bash
make test PYTEST_ARGS="tests/refact/test_verification_plan.py tests/refact/test_shadow_run.py tests/refact/test_run_cli.py tests/lineage/test_job_dag.py -q"
make test
```

Expected: PASS.

- [ ] **Step 2: Validate against shop assets**

Regenerate shop lineage with the supported extractor, assert
`warehouses/shop/artifacts/lineage/job_dag.json` does not exist, build the
shop dependency plan from the real `lineage_data.json`, and verify:

```text
dependency keys == jobs_to_run names
scheduler == plan
warnings absent
topological dependency constraints hold
at least one ready layer contains multiple jobs
```

- [ ] **Step 3: Perform code review**

Review the final diff for dependency direction, induced-subgraph correctness,
case-insensitive matching, fail-fast timing, mutation safety, deterministic
JSON, and test gaps. Fix findings and rerun affected verification commands.

- [ ] **Step 4: Report results**

Summarize changed files, test output, real shop graph statistics, and any
remaining operational limitation such as unavailable Doris credentials.
