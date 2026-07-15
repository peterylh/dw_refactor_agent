# Process Table Job Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate strict lineage JSON v2 with first-class Jobs and Job-owned edges, isolate same-name local process tables, resolve unique cross-job process-table producers, and derive an explainable Job DAG v2.

**Architecture:** SQL extraction first emits per-Job read/write/lifecycle facts and direct edges. A focused Job-lineage resolver uses canonical qualified identifiers, local-producer precedence, and unique external producer matching to build dependencies and diagnostics. Public lineage artifacts store Jobs, tables, Job-owned edges, and diagnostics; graph, DAG, import, query, and execution consumers read that contract through backward-compatible domain models.

**Tech Stack:** Python 3.7, sqlglot Doris dialect, dataclasses, JSON, Doris OLAP DDL, pytest 7 through the project Makefile.

## Global Constraints

- Do not introduce `logical_process_id` or cross-run process-table rename matching.
- New lineage artifacts use `format_version: 2`.
- Version 2 edges contain `job` and never contain `source_file`; SQL paths live on `jobs[].source_file`.
- Public tables use `dataset_type = managed|process|temporary|external`; do not add `lineage_scope`.
- Local process matching uses the internal key `(job, canonical_fqn)` and never leaks into the public schema.
- Only a unique eligible external producer creates cross-Job lineage; zero or multiple candidates create diagnostics and no guessed dependency.
- `CREATE TEMPORARY TABLE` and ordinary tables dropped after creation in the same Job are not eligible external producers.
- `DROP IF EXISTS; CREATE TABLE/CTAS` without a later DROP remains an eligible persistent output.
- Identifier comparison is case-insensitive through the existing canonical/casefold helpers; display casing is preserved.
- New readers accept version 1 lineage and DAG artifacts; new writers emit version 2 only.
- Run tests through `make test`; do not invoke bare `pytest`.

---

## File Structure

- Create `src/dw_refactor_agent/lineage/job_lineage.py`: Job naming, Job records, producer resolution, dependency evidence, and structured producer diagnostics.
- Create `src/dw_refactor_agent/lineage/contract.py`: strict lineage v2 and Job DAG v2 validators without adding a JSON-schema dependency.
- Modify `src/dw_refactor_agent/lineage/sql_task_facts.py`: collect input tables and distinguish persistent, temporary, and created-then-dropped outputs.
- Modify `src/dw_refactor_agent/lineage/task_cache.py`: cache the expanded task facts and invalidate legacy cache entries safely.
- Modify `src/dw_refactor_agent/lineage/lineage_extractor.py`: build tables with `dataset_type`, explicit Jobs, Job-owned edges, diagnostics, and validate v2 before writing.
- Modify `src/dw_refactor_agent/lineage/model.py`: parse v1/v2 Jobs, tables, and edges through one compatibility boundary.
- Modify `src/dw_refactor_agent/lineage/asset_graph.py`: scope process-table traversal by Job and cross Jobs only through resolved unique producers.
- Modify `src/dw_refactor_agent/lineage/job_dag.py`: serialize Job DAG v2 and load legacy DAGs.
- Modify `src/dw_refactor_agent/execution/task_run.py` and `src/dw_refactor_agent/refactor/verification_plan.py`: consume explicit Job DAG nodes.
- Modify `src/dw_refactor_agent/lineage/view.py`, `query.py`, `refresh_lineage_html.py`, and `lineage_cli.py`: resolve SQL source paths through Jobs and add strict artifact validation.
- Modify `src/dw_refactor_agent/lineage/import_lineage.py`: import explicit Jobs, Job-owned edges, `dataset_type`, and Job inputs/outputs.
- Create `src/dw_refactor_agent/lineage/ddl/job_dataset.sql` and modify `table_info.sql` plus snapshot/import table lists.
- Add or modify focused tests under `tests/lineage/`, `tests/test_task_run.py`, and `tests/refact/`.

---

### Task 1: Task facts and producer resolution

**Files:**
- Create: `src/dw_refactor_agent/lineage/job_lineage.py`
- Modify: `src/dw_refactor_agent/lineage/sql_task_facts.py`
- Modify: `src/dw_refactor_agent/lineage/task_cache.py`
- Test: `tests/lineage/test_sql_task_facts.py`
- Create: `tests/lineage/test_job_lineage.py`

**Interfaces:**
- Produces: `job_name_from_source_file(source_file: str) -> str`
- Produces: `build_job_records(task_results: Sequence[dict], display_table: Callable[[str], str]) -> list[dict]`
- Produces: `resolve_job_dependencies(jobs: Sequence[dict], tables: Sequence[dict]) -> tuple[list[dict], list[dict]]`
- Produces task-result fields: `input_tables`, `output_tables`, `created_tables`, `temporary_tables`, and `local_lifecycle_tables`.

- [ ] **Step 1: Write failing lifecycle and resolver tests**

```python
def test_pre_drop_create_without_post_drop_is_persistent():
    facts = extract_task_table_facts(
        "DROP TABLE IF EXISTS tmp_t; CREATE TABLE tmp_t AS SELECT * FROM src",
        "prepare.sql",
    )
    assert facts["input_tables"] == {"src"}
    assert facts["output_tables"] == {"tmp_t"}
    assert facts["local_lifecycle_tables"] == []


def test_unique_external_process_producer_builds_dependency():
    dependencies, diagnostics = resolve_job_dependencies(
        [
            {"name": "a", "inputs": ["db.src"], "outputs": ["db.t"]},
            {"name": "b", "inputs": ["db.t"], "outputs": ["db.out"]},
        ],
        [{"full_name": "db.t", "dataset_type": "process"}],
    )
    assert dependencies == [
        {
            "upstream_job": "a",
            "downstream_job": "b",
            "datasets": ["db.t"],
        }
    ]
    assert diagnostics == []
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `make test PYTEST_ARGS='tests/lineage/test_sql_task_facts.py tests/lineage/test_job_lineage.py -q'`

Expected: FAIL because `input_tables`, `local_lifecycle_tables`, and `job_lineage` do not exist.

- [ ] **Step 3: Implement task facts and resolver**

Implement statement-level read collection that skips only the actual write-target AST node, excludes CTE aliases, and preserves self-reads. Change transient classification so only `CREATE TEMPORARY` and a post-create DROP become local lifecycle facts. Implement local-producer precedence and canonical unique-producer matching in `job_lineage.py`; aggregate multiple datasets for the same Job pair and emit `not_found` or `multiple_candidates` diagnostics only for process/temporary datasets.

- [ ] **Step 4: Persist expanded facts in task-cache entries**

Add all new fact fields to task results and cache entries. Cache reads missing those fields must miss or safely reconstruct rather than silently emit incomplete Jobs.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `make test PYTEST_ARGS='tests/lineage/test_sql_task_facts.py tests/lineage/test_job_lineage.py tests/lineage/test_task_cache.py -q'`

Expected: all selected tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dw_refactor_agent/lineage/sql_task_facts.py src/dw_refactor_agent/lineage/task_cache.py src/dw_refactor_agent/lineage/job_lineage.py tests/lineage/test_sql_task_facts.py tests/lineage/test_job_lineage.py tests/lineage/test_task_cache.py
git commit -m "feat(lineage): resolve process table job producers"
```

### Task 2: Strict v2 domain and artifact contract

**Files:**
- Create: `src/dw_refactor_agent/lineage/contract.py`
- Modify: `src/dw_refactor_agent/lineage/model.py`
- Create: `tests/lineage/test_lineage_contract.py`
- Test: `tests/lineage/test_lineage_view.py`

**Interfaces:**
- Produces: `validate_lineage_v2(data: dict) -> None`
- Produces: `validate_job_dag_v2(data: dict) -> None`
- Produces: `LineageTable.dataset_type: str`
- Produces: `LineageJob.inputs: tuple[str, ...]` and `outputs: tuple[str, ...]`
- Produces: `LineageEdge.job: str`; keeps `source_file` only as a v1 compatibility read field.

- [ ] **Step 1: Write failing strict-contract tests**

```python
def test_v2_edge_requires_job_and_rejects_source_file():
    data = valid_lineage_v2()
    data["edges"][0]["source_file"] = "job.sql"
    with pytest.raises(LineageContractError, match="source_file"):
        validate_lineage_v2(data)


def test_v2_edge_job_must_exist():
    data = valid_lineage_v2()
    data["edges"][0]["job"] = "missing"
    with pytest.raises(LineageContractError, match="missing"):
        validate_lineage_v2(data)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `make test PYTEST_ARGS='tests/lineage/test_lineage_contract.py -q'`

Expected: FAIL because the contract module does not exist.

- [ ] **Step 3: Implement strict validators and v1/v2 model parsing**

Validate exact required top-level keys, enum values, Job uniqueness, sorted unique I/O arrays, typed edge refs, forbidden v2 `source_file`, and Job references. Keep unknown extension fields rejected for strict v2 output. In `LineageSnapshot.from_dict`, prefer explicit Jobs for v2; for v1 derive Jobs from edge `source_file` and preserve safe legacy transient behavior.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `make test PYTEST_ARGS='tests/lineage/test_lineage_contract.py tests/lineage/test_lineage_view.py -q'`

Expected: selected tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dw_refactor_agent/lineage/contract.py src/dw_refactor_agent/lineage/model.py tests/lineage/test_lineage_contract.py tests/lineage/test_lineage_view.py
git commit -m "feat(lineage): add strict lineage v2 contract"
```

### Task 3: Extract lineage JSON v2

**Files:**
- Modify: `src/dw_refactor_agent/lineage/lineage_extractor.py`
- Modify: `src/dw_refactor_agent/lineage/task_cache.py`
- Test: `tests/lineage/test_lineage_output_metadata.py`
- Test: `tests/lineage/test_lineage_extraction_performance.py`
- Test: `tests/lineage/test_lineage_extractor_summary.py`

**Interfaces:**
- Changes: `build_lineage_output(all_lineage, schema, *, task_results=None, diagnostics=None) -> dict`
- Consumes: Task 1 Job records and producer diagnostics.
- Consumes: Task 2 strict validator.
- Produces: strict v2 `{format_version,tables,jobs,edges,diagnostics}`.

- [ ] **Step 1: Write failing v2 output tests**

```python
def test_build_lineage_output_emits_job_owned_edges_without_source_file():
    output = build_lineage_output(
        [lineage_entry(source_file="mid/tasks/prepare.sql")],
        schema,
        task_results=[task_result("mid/tasks/prepare.sql")],
    )
    assert output["format_version"] == 2
    assert output["jobs"][0]["name"] == "prepare"
    assert output["edges"][0]["job"] == "prepare"
    assert "source_file" not in output["edges"][0]
    validate_lineage_v2(output)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `make test PYTEST_ARGS='tests/lineage/test_lineage_output_metadata.py tests/lineage/test_lineage_extractor_summary.py -q'`

Expected: FAIL because the extractor still writes v1 tables and edge `source_file`.

- [ ] **Step 3: Implement v2 serialization**

Build Job names once from task source paths; reject duplicate names. Map every raw entry source path to a Job, serialize only `job` on each edge, classify tables with `dataset_type`, normalize diagnostics to Job references, and validate the complete artifact before any file write. Remove global transient-table metadata from v2.

- [ ] **Step 4: Update cache/extractor version and summaries**

Invalidate old task cache entries after fact-schema changes. Update CLI counts from transient booleans to dataset types and include producer warning counts.

- [ ] **Step 5: Run extraction tests and performance guard**

Run: `make test PYTEST_ARGS='tests/lineage/test_lineage_output_metadata.py tests/lineage/test_lineage_extractor_summary.py tests/lineage/test_lineage_extraction_performance.py -q'`

Expected: selected tests PASS and performance assertions remain within their current thresholds.

- [ ] **Step 6: Commit**

```bash
git add src/dw_refactor_agent/lineage/lineage_extractor.py src/dw_refactor_agent/lineage/task_cache.py tests/lineage/test_lineage_output_metadata.py tests/lineage/test_lineage_extractor_summary.py tests/lineage/test_lineage_extraction_performance.py
git commit -m "feat(lineage): emit job-aware lineage v2"
```

### Task 4: Job-scoped asset traversal

**Files:**
- Modify: `src/dw_refactor_agent/lineage/asset_graph.py`
- Modify: `src/dw_refactor_agent/lineage/table_graph.py`
- Modify: `src/dw_refactor_agent/lineage/view.py`
- Modify: `src/dw_refactor_agent/lineage/query.py`
- Test: `tests/lineage/test_asset_graph.py`
- Test: `tests/lineage/test_lineage_query.py`
- Test: `tests/lineage/test_lineage_view.py`

**Interfaces:**
- Consumes: `edge.job`, explicit Jobs, and resolved dependency evidence.
- Produces: local process traversal keyed internally by `(job, canonical_table)`.

- [ ] **Step 1: Write the same-name regression test**

```python
def test_same_name_local_process_tables_do_not_cross_jobs():
    upstream, downstream = build_asset_table_graph(two_local_t_jobs_v2())
    assert downstream["src_a"] == {"out_a"}
    assert downstream["src_b"] == {"out_b"}
    assert "out_b" not in downstream["src_a"]
    assert "out_a" not in downstream["src_b"]
```

Also add a unique shared-process test proving `src -> t` in Job A and `t -> out` in Job B produces `src -> out`, while multiple producers produce no composed path.

- [ ] **Step 2: Run tests and verify RED**

Run: `make test PYTEST_ARGS='tests/lineage/test_asset_graph.py tests/lineage/test_lineage_query.py -q'`

Expected: the same-name regression shows the current cross-product.

- [ ] **Step 3: Implement scoped traversal**

Replace global transient-name collapsing with per-Job process occurrence routing. A consumer with a local incoming process edge uses only that Job's producer edge; otherwise use only the dependency resolver's unique producer. Keep managed/external assets as global nodes and preserve condition lineage semantics.

- [ ] **Step 4: Resolve file paths through Jobs**

Update view and query records to expose Job and, where a display still needs the SQL path, resolve `job -> jobs[].source_file`. Do not re-add `source_file` to Edge data.

- [ ] **Step 5: Run graph/query tests and verify GREEN**

Run: `make test PYTEST_ARGS='tests/lineage/test_asset_graph.py tests/lineage/test_lineage_query.py tests/lineage/test_lineage_view.py -q'`

Expected: selected tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dw_refactor_agent/lineage/asset_graph.py src/dw_refactor_agent/lineage/table_graph.py src/dw_refactor_agent/lineage/view.py src/dw_refactor_agent/lineage/query.py tests/lineage/test_asset_graph.py tests/lineage/test_lineage_query.py tests/lineage/test_lineage_view.py
git commit -m "fix(lineage): isolate same-name process table paths"
```

### Task 5: Job DAG v2 and execution consumers

**Files:**
- Modify: `src/dw_refactor_agent/lineage/job_dag.py`
- Modify: `src/dw_refactor_agent/execution/task_run.py`
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`
- Test: `tests/lineage/test_job_dag.py`
- Test: `tests/test_task_run.py`
- Test: `tests/refact/test_verification_plan.py`

**Interfaces:**
- Produces: `job_dag_from_lineage(lineage_data: dict) -> JobDAG`
- Produces Job DAG v2 fields: `format_version`, `jobs`, `data_dependencies`, `deps`, and `rev`.
- Keeps: `JobDAG.from_dict()` compatibility with legacy `edges/self_edges/deps/rev`.

- [ ] **Step 1: Write failing DAG v2 tests**

```python
def test_job_dag_v2_uses_explicit_jobs_and_dataset_evidence():
    dag = job_dag_from_lineage(shared_process_lineage_v2())
    assert dag.to_dict() == {
        "format_version": 2,
        "jobs": ["build_report", "prepare_sales"],
        "data_dependencies": [{
            "upstream_job": "prepare_sales",
            "downstream_job": "build_report",
            "datasets": ["internal.shop_dm.t"],
        }],
        "deps": {"build_report": [], "prepare_sales": ["build_report"]},
        "rev": {"build_report": ["prepare_sales"], "prepare_sales": []},
    }
```

Add tests for isolated Jobs, self-read/write, ambiguous producers, Job names unrelated to outputs, and v1 load compatibility.

- [ ] **Step 2: Run tests and verify RED**

Run: `make test PYTEST_ARGS='tests/lineage/test_job_dag.py tests/test_task_run.py -q'`

Expected: FAIL because the current DAG treats table names as Job nodes.

- [ ] **Step 3: Implement DAG v2 and migrate consumers**

Construct dependencies with Task 1's resolver, initialize empty adjacency entries for every Job, aggregate dataset evidence, validate v2 before save, and adapt task execution/refactor planning to explicit Job names. Preserve old DAG load semantics for existing artifacts.

- [ ] **Step 4: Run DAG and execution tests**

Run: `make test PYTEST_ARGS='tests/lineage/test_job_dag.py tests/test_task_run.py tests/refact/test_verification_plan.py -q'`

Expected: selected tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dw_refactor_agent/lineage/job_dag.py src/dw_refactor_agent/execution/task_run.py src/dw_refactor_agent/refactor/verification_plan.py tests/lineage/test_job_dag.py tests/test_task_run.py tests/refact/test_verification_plan.py
git commit -m "feat(lineage): generate explicit job dag v2"
```

### Task 6: Import, DDL, CLI, and HTML compatibility

**Files:**
- Create: `src/dw_refactor_agent/lineage/ddl/job_dataset.sql`
- Modify: `src/dw_refactor_agent/lineage/ddl/table_info.sql`
- Modify: `src/dw_refactor_agent/lineage/ddl/lineage_snapshot.sql`
- Modify: `src/dw_refactor_agent/lineage/import_lineage.py`
- Modify: `src/dw_refactor_agent/lineage/lineage_cli.py`
- Modify: `src/dw_refactor_agent/lineage/refresh_lineage_html.py`
- Test: `tests/lineage/test_import_lineage.py`
- Test: `tests/lineage/test_lineage_ddl.py`
- Test: `tests/lineage/test_lineage_cli.py`
- Test: `tests/lineage/test_refresh_lineage_html.py`

**Interfaces:**
- Adds: `LineageImportRows.job_dataset_rows`.
- Adds CLI: `lineage_cli validate --project <project>`.
- Consumes: `edge.job -> jobs[].name -> source_file`.

- [ ] **Step 1: Write failing import/DDL/CLI tests**

Assert table rows contain `dataset_type`, Job rows come from explicit Jobs, edge Job IDs are resolved by name, `job_dataset` INPUT/OUTPUT rows are complete, v2 edges without `source_file` import successfully, and `lineage_cli validate` rejects a forbidden edge `source_file`.

- [ ] **Step 2: Run tests and verify RED**

Run: `make test PYTEST_ARGS='tests/lineage/test_import_lineage.py tests/lineage/test_lineage_ddl.py tests/lineage/test_lineage_cli.py -q'`

Expected: FAIL because the importer and DDL still use transient fields and source-file edge lookup.

- [ ] **Step 3: Implement additive DDL and v2 import**

Add `dataset_type`, create `job_dataset`, include it in snapshot cleanup/verification/counts, build Job IDs from explicit Job records, and map every edge by `job`. Keep a v1 normalization path that derives Job names from legacy edge source files before row construction.

- [ ] **Step 4: Update CLI/HTML source lookup**

Add strict validation command and resolve SQL links through Jobs. Ensure serialized HTML data remains v2 and does not synthesize Edge `source_file`.

- [ ] **Step 5: Run compatibility tests and verify GREEN**

Run: `make test PYTEST_ARGS='tests/lineage/test_import_lineage.py tests/lineage/test_lineage_ddl.py tests/lineage/test_lineage_cli.py tests/lineage/test_refresh_lineage_html.py -q'`

Expected: selected tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dw_refactor_agent/lineage/ddl src/dw_refactor_agent/lineage/import_lineage.py src/dw_refactor_agent/lineage/lineage_cli.py src/dw_refactor_agent/lineage/refresh_lineage_html.py tests/lineage/test_import_lineage.py tests/lineage/test_lineage_ddl.py tests/lineage/test_lineage_cli.py tests/lineage/test_refresh_lineage_html.py
git commit -m "feat(lineage): import and validate lineage v2"
```

### Task 7: Generate and strictly validate shop artifacts

**Files:**
- Generate: `warehouses/shop/artifacts/lineage/lineage_data.json`
- Generate: `warehouses/shop/artifacts/lineage/job_dag.json`
- Generate through existing refresh flow: shop lineage HTML artifacts if tracked by the project.
- Test: all affected test modules and full non-API suite.

**Interfaces:**
- Consumes: strict lineage and Job DAG validators.
- Produces: reproducible shop v2 artifacts.

- [ ] **Step 1: Run all focused tests**

Run: `make test PYTEST_ARGS='tests/lineage tests/test_task_run.py tests/refact/test_verification_plan.py -q -m "not api"'`

Expected: all focused tests PASS.

- [ ] **Step 2: Generate shop lineage without cache**

Run: `PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.lineage_extractor --project shop --no-cache`

Expected: command exits 0 and writes lineage JSON v2.

- [ ] **Step 3: Generate Job DAG v2 and refresh HTML**

Use the project DAG generation path consumed by `task_run --refresh-dag --validate-only`, then run `python -m dw_refactor_agent.lineage.refresh_lineage_html --project shop` through the configured conda environment.

Expected: `job_dag.json` has format version 2 and HTML refresh exits 0.

- [ ] **Step 4: Strictly validate generated JSON**

Run: `PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.lineage_cli validate --project shop`

Expected: reports both lineage JSON v2 and Job DAG v2 valid; every Edge has an existing `job`, no v2 Edge has `source_file`, Job names are unique, enum values are valid, adjacency is symmetric, and dependency evidence matches `deps/rev`.

- [ ] **Step 5: Run the complete non-API suite**

Run: `make test`

Expected: all non-API tests PASS.

- [ ] **Step 6: Commit generated artifacts and final fixes**

```bash
git add warehouses/shop/artifacts/lineage src tests
git commit -m "fix(lineage): prevent process table cross-job contamination"
```

### Task 8: Final Code Review and verification

**Files:**
- Review: all changes from the design commit through HEAD.
- Modify: only files required to fix concrete review findings.

**Interfaces:**
- Consumes: committed implementation and fresh test/generation evidence.
- Produces: severity-ranked Review findings or an explicit clean Review.

- [ ] **Step 1: Inspect the complete diff and generated artifacts**

Review identifier canonicalization, process-table eligibility, Job-reference integrity, v1 compatibility, DAG direction, import row mapping, and absence of Edge `source_file`.

- [ ] **Step 2: Run a dedicated Code Review**

Use `superpowers:requesting-code-review` against the design base commit and current HEAD. Findings must cite exact files and lines and prioritize correctness/regressions over style.

- [ ] **Step 3: Fix every confirmed finding with a regression test**

For each accepted issue, first add a failing test, reproduce it through `make test PYTEST_ARGS=...`, apply the minimal fix, and rerun the focused suite.

- [ ] **Step 4: Re-run strict generation and full verification**

Repeat shop no-cache extraction, DAG generation, strict CLI validation, and `make test` after Review fixes.

- [ ] **Step 5: Commit Review fixes**

```bash
git add src tests warehouses/shop/artifacts/lineage
git commit -m "fix(lineage): address process lineage review findings"
```

- [ ] **Step 6: Report evidence**

Report generated artifact paths, format versions, Job/table/edge/dependency/diagnostic counts, strict validation result, full test result, Review findings and fixes, and remaining explicitly unsupported cases.
