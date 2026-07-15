# Cross-Job Process Table Scenarios Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make an existing producer and consumer in both `shop` and `retail_banking` hand data across Jobs through a persistent process table, then prove lineage v2 and Job DAG v2 resolve the handoff correctly.

**Architecture:** Warehouse process handoffs are verified through the existing
extractor, strict contract, Job dependency resolver, DAG builder, and column
query; no project-specific lineage algorithm is added. The delivered safety
layer also refreshes lineage before every execution plan, fails closed on
unresolved selected process producers, and locks SQL by physical Doris target.
Scenario, warehouse-asset guard, execution planner, and run-lock tests live at
their owning boundaries. Both projects keep base and window-companion Job I/O
equivalent.

**Tech Stack:** Doris SQL, Python 3.7, sqlglot-based lineage extraction, pytest, lineage v2, Job DAG v2.

---

## File structure and ownership

- `warehouses/shop/mid/tasks/dws_store_sales_daily.sql`: owns the shop stage
  table build and managed DWS materialization.
- `warehouses/shop/mid/tasks/dim_store_metric_snapshot.sql`: consumes the shop
  process table.
- `warehouses/shop/mid/tasks/full_refresh/dws_store_sales_daily_full_refresh.sql`
  and `dim_store_metric_snapshot_full_refresh.sql`: implement the same handoff
  for one configured date window.
- `warehouses/retail_banking/mid/tasks/dws_client_transaction_daily.sql`:
  owns the retail banking incremental stage table build and managed DWS
  materialization.
- `warehouses/retail_banking/ads/tasks/ads_customer_transaction_kpi_daily.sql`:
  consumes the retail banking incremental process table.
- `warehouses/retail_banking/mid/tasks/full_refresh/dws_client_transaction_daily_full_refresh.sql`:
  owns the full-refresh process-table variant.
- `warehouses/retail_banking/ads/tasks/full_refresh/ads_customer_transaction_kpi_daily_full_refresh.sql`:
  consumes the full-refresh process table.
- `warehouses/retail_banking/semantic_specs/dws_ads.yaml`: authoritative
  `process_table_handoff` contract for generated retail banking SQL.
- `warehouses/retail_banking/tools/generate_assets.py`: single generator for
  retail banking base/full-refresh producer and consumer assets.
- `tests/lineage/test_cross_job_process_scenarios.py`: hermetic acceptance of
  the two checked-in scenarios through existing lineage interfaces.
- `tests/test_process_table_assets.py`: Doris CTAS and immutable process-output
  asset guards.
- `tests/test_execution_planner.py`: real shop companion planning assertions.
- `src/dw_refactor_agent/execution/task_run.py` and `run_lock.py`: fresh
  lineage fail-closed planning and physical-target execution serialization.

No managed DDL/model file is created for either process table. No core lineage
module is expected to change. If the scenarios expose a core defect, add the
smallest regression in the owning existing test module before changing that
module.

## Implemented outcome and review hardening

The initial “only assets and one test” scope did not describe the final safety
surface. The implemented result keeps producer resolution and graph traversal
unchanged, while adding safeguards only at the execution boundary:

- every plan refreshes current SQL lineage and builds its DAG from the same v2
  payload;
- resolved process dependencies require producer closure, and existing
  `UNRESOLVED_DATASET_PRODUCER` diagnostics block selected consumers;
- SQL runs serialize by canonical `(host, port, database)` across checkouts on
  one host, with the same absolute `DW_REFACTOR_AGENT_RUN_LOCK_DIR` on every
  executor when a shared lock location is required;
- shop uses base plus window companions, with cleanup folded into an immutable
  single-replica CTAS;
- retail banking uses `semantic_specs/dws_ads.yaml` and
  `tools/generate_assets.py` as its single generation source; checked-in SQL is
  generated output, not a second hand-maintained implementation;
- cross-Job lineage acceptance remains in the lineage scenario module, SQL
  asset constraints live in `tests/test_process_table_assets.py`, and companion
  invocation behavior lives in `tests/test_execution_planner.py`.

### Task 1: Add the hermetic project-scenario acceptance test

**Files:**
- Create: `tests/lineage/test_cross_job_process_scenarios.py`
- Read: `docs/development/sql_dev_standards.md`
- Read: `src/dw_refactor_agent/lineage/AGENTS.md`

- [ ] **Step 1: Add a real-asset extraction helper and scenario records**

Create the test module with one immutable scenario record per project. Use the
existing public/configured paths and lineage functions:

```python
from dataclasses import dataclass

import pytest

from dw_refactor_agent.config import (
    project_dir as configured_project_dir,
    task_source_file,
)
from dw_refactor_agent.lineage.contract import validate_lineage_v2
from dw_refactor_agent.lineage.job_dag import job_dag_from_lineage
from dw_refactor_agent.lineage.lineage_extractor import (
    build_lineage_output,
    build_schema_from_project_ddl,
    configure_project,
    extract_lineage_from_task_files,
)
from dw_refactor_agent.lineage.query import build_column_lineage
from dw_refactor_agent.lineage.view import LineageView


@dataclass(frozen=True)
class Scenario:
    project: str
    producer_task: str
    consumer_task: str
    producer_job: str
    consumer_job: str
    process_table: str
    upstream_column: str
    process_column: str
    target_table: str
    target_column: str
    producer_companion: str = ""
    consumer_companion: str = ""


SCENARIOS = (
    Scenario(
        project="shop",
        producer_task="mid/tasks/dws_store_sales_daily.sql",
        consumer_task="mid/tasks/dim_store_metric_snapshot.sql",
        producer_job="dws_store_sales_daily",
        consumer_job="dim_store_metric_snapshot",
        process_table="shop_dm.stage_store_sales_daily",
        upstream_column="dwd_order_detail.order_id",
        process_column="stage_store_sales_daily.order_count",
        target_table="dim_store_metric_snapshot",
        target_column="store_order_count",
        producer_companion=(
            "mid/tasks/full_refresh/"
            "dws_store_sales_daily_full_refresh.sql"
        ),
        consumer_companion=(
            "mid/tasks/full_refresh/"
            "dim_store_metric_snapshot_full_refresh.sql"
        ),
    ),
    Scenario(
        project="retail_banking",
        producer_task="mid/tasks/dws_client_transaction_daily.sql",
        consumer_task="ads/tasks/ads_customer_transaction_kpi_daily.sql",
        producer_job="dws_client_transaction_daily",
        consumer_job="ads_customer_transaction_kpi_daily",
        process_table="retail_banking_dm.stage_client_transaction_daily",
        upstream_column="dwd_client_transaction.amount",
        process_column="stage_client_transaction_daily.total_amount",
        target_table="ads_customer_transaction_kpi_daily",
        target_column="total_amount",
        producer_companion=(
            "mid/tasks/full_refresh/"
            "dws_client_transaction_daily_full_refresh.sql"
        ),
        consumer_companion=(
            "ads/tasks/full_refresh/"
            "ads_customer_transaction_kpi_daily_full_refresh.sql"
        ),
    ),
)


def _extract_tasks(project, relative_paths):
    configure_project(project)
    project_dir = configured_project_dir(project)
    assert project_dir is not None
    task_files = [project_dir / path for path in relative_paths]
    assert all(path.exists() for path in task_files)
    schema = build_schema_from_project_ddl(project)
    result = extract_lineage_from_task_files(
        task_files,
        project_dir,
        schema,
        parallel=1,
        source_file_for_path=lambda path: task_source_file(project, path),
    )
    assert result["errors"] == []
    return result, schema


def _scenario_lineage(scenario):
    result, schema = _extract_tasks(
        scenario.project,
        (scenario.producer_task, scenario.consumer_task),
    )
    data = build_lineage_output(
        result["lineage"],
        schema,
        task_results=result["task_results"],
    )
    validate_lineage_v2(data)
    return data
```

- [ ] **Step 2: Assert process type, Job I/O, dependency evidence, and field path**

Add the parameterized acceptance. It must call the existing DAG and query
interfaces rather than inspecting or traversing a separately built graph:

```python
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item.project)
def test_checked_in_cross_job_process_table_scenario(scenario):
    data = _scenario_lineage(scenario)
    tables = {table["full_name"]: table for table in data["tables"]}
    jobs = {job["name"]: job for job in data["jobs"]}

    assert tables[scenario.process_table]["dataset_type"] == "process"
    assert scenario.process_table in jobs[scenario.producer_job]["outputs"]
    assert scenario.process_table in jobs[scenario.consumer_job]["inputs"]
    assert not [
        item
        for item in data["diagnostics"]
        if item["dataset"] == scenario.process_table
    ]
    assert all("source_file" not in edge for edge in data["edges"])

    dag = job_dag_from_lineage(data)
    assert dag.data_dependencies == [
        {
            "upstream_job": scenario.producer_job,
            "downstream_job": scenario.consumer_job,
            "datasets": [scenario.process_table],
        }
    ]

    result = build_column_lineage(
        LineageView.from_data(scenario.project, data),
        scenario.target_table,
        scenario.target_column,
        direction="upstream",
        depth=4,
    )
    assert any(
        scenario.upstream_column in path.nodes
        and scenario.process_column in path.nodes
        for path in result.paths
    )
```

- [ ] **Step 3: Assert both projects' base/companion Job I/O equivalence**

Add a fact-normalization helper and compare the producer and consumer variants:

```python
def _io_by_position(project, relative_paths):
    result, _schema = _extract_tasks(project, relative_paths)
    return [
        (
            set(task_result["input_tables"]),
            set(task_result["output_tables"]),
        )
        for task_result in result["task_results"]
    ]


@pytest.mark.parametrize(
    "scenario",
    [item for item in SCENARIOS if item.producer_companion],
    ids=lambda item: item.project,
)
def test_full_refresh_companions_keep_process_job_io_equivalent(scenario):
    base_io = _io_by_position(
        scenario.project,
        (scenario.producer_task, scenario.consumer_task),
    )
    companion_io = _io_by_position(
        scenario.project,
        (scenario.producer_companion, scenario.consumer_companion),
    )
    assert companion_io == base_io
```

- [ ] **Step 4: Run the test and verify RED**

Run:

```bash
make test PYTEST_ARGS='tests/lineage/test_cross_job_process_scenarios.py -q'
```

Expected: FAIL because the consumers still read managed DWS tables and the
retail banking process table does not exist.

- [ ] **Step 5: Commit the RED test**

```bash
git add tests/lineage/test_cross_job_process_scenarios.py
git commit -m "test(lineage): cover cross-job process scenarios"
```

### Task 2: Make the shop process table the real Job handoff

**Files:**
- Modify: `warehouses/shop/mid/tasks/dws_store_sales_daily.sql`
- Modify: `warehouses/shop/mid/tasks/dim_store_metric_snapshot.sql`
- Modify: `warehouses/shop/mid/tasks/full_refresh/dws_store_sales_daily_full_refresh.sql`
- Modify: `warehouses/shop/mid/tasks/full_refresh/dim_store_metric_snapshot_full_refresh.sql`
- Test: `tests/lineage/test_cross_job_process_scenarios.py`
- Test: `tests/test_process_table_assets.py`
- Test: `tests/test_execution_planner.py`

- [ ] **Step 1: Build one immutable process-table snapshot in the producer**

Build both the base slice and full-refresh window with a single-replica CTAS.
Fold cleanup into its SELECT so nothing mutates the process table after CTAS:

```sql
SET @etl_date = COALESCE(@etl_date, CURDATE());

DROP TABLE IF EXISTS shop_dm.stage_store_sales_daily;
CREATE TABLE shop_dm.stage_store_sales_daily
PROPERTIES ("replication_num" = "1")
AS
SELECT
    store_id,
    order_date AS stat_date,
    COUNT(DISTINCT order_id) AS order_count,
    COUNT(DISTINCT customer_id) AS customer_count,
    SUM(subtotal) AS total_amount,
    COALESCE(SUM(discount), 0.00) AS discount_amount,
    SUM(subtotal - discount) AS payment_amount,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
WHERE IF(
    @full_refresh = 1,
    1 = 1,
    order_date = CAST(@etl_date AS DATE)
)
GROUP BY store_id, order_date
HAVING COUNT(DISTINCT order_id) <> 0
   AND (
       SUM(subtotal - discount) IS NULL
       OR SUM(subtotal - discount) >= 0
   );

DELETE FROM shop_dm.dws_store_sales_daily
WHERE IF(
    @full_refresh = 1,
    1 = 1,
    stat_date = CAST(@etl_date AS DATE)
);

INSERT INTO shop_dm.dws_store_sales_daily (
    store_id,
    stat_date,
    order_count,
    customer_count,
    total_amount,
    discount_amount,
    payment_amount,
    etl_time
)
SELECT
    store_id,
    stat_date,
    order_count,
    customer_count,
    total_amount,
    discount_amount,
    payment_amount,
    etl_time
FROM shop_dm.stage_store_sales_daily;
```

Do not mutate or drop the stage table after CTAS. The window companion uses the
same projection and `HAVING`, replacing the slice predicate with the configured
`@etl_start_date`/`@etl_end_date` interval.

- [ ] **Step 2: Point the existing consumer to the process table**

In `dim_store_metric_snapshot.sql`, change only the sales-side relation:

```sql
LEFT JOIN shop_dm.stage_store_sales_daily ss
    ON s.store_id = ss.store_id
    AND s.snapshot_date = ss.stat_date
```

Keep the existing target, slice deletion, store source, metrics, and grain.
Apply the same source handoff and date window to the consumer companion.

- [ ] **Step 3: Run the shop scenario and SQL-related regression tests**

Run:

```bash
make test PYTEST_ARGS='tests/lineage/test_cross_job_process_scenarios.py::test_checked_in_cross_job_process_table_scenario[shop] tests/lineage/test_sql_task_facts.py tests/lineage/test_lineage_output_metadata.py -q'
```

Expected: the shop scenario PASS; the retail banking parameter remains RED
until Task 3.

- [ ] **Step 4: Commit the shop assets**

```bash
git add warehouses/shop/mid/tasks/dws_store_sales_daily.sql warehouses/shop/mid/tasks/dim_store_metric_snapshot.sql
git commit -m "feat(shop): hand off store metrics through process table"
```

### Task 3: Make the retail banking process table the real Job handoff

**Files:**
- Modify source: `warehouses/retail_banking/semantic_specs/dws_ads.yaml`
- Modify generator: `warehouses/retail_banking/tools/generate_assets.py`
- Regenerate: `warehouses/retail_banking/mid/tasks/dws_client_transaction_daily.sql`
- Regenerate: `warehouses/retail_banking/ads/tasks/ads_customer_transaction_kpi_daily.sql`
- Regenerate: `warehouses/retail_banking/mid/tasks/full_refresh/dws_client_transaction_daily_full_refresh.sql`
- Regenerate: `warehouses/retail_banking/ads/tasks/full_refresh/ads_customer_transaction_kpi_daily_full_refresh.sql`
- Test: `tests/lineage/test_cross_job_process_scenarios.py`

`semantic_specs/dws_ads.yaml` is authoritative. Set
`process_table_handoff: stage_client_transaction_daily` on the reviewed DWS
spec and let `tools/generate_assets.py` render both producer variants and route
the generated ADS source to that handoff. Do not patch the four generated SQL
files as an independent implementation.

- [ ] **Step 1: Build the incremental process table and materialize DWS from it**

Keep the existing aggregation expressions and grain, but make CTAS the first
materialization:

```sql
SET @etl_date = COALESCE(@etl_date, CURDATE());

DROP TABLE IF EXISTS retail_banking_dm.stage_client_transaction_daily;
CREATE TABLE retail_banking_dm.stage_client_transaction_daily AS
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`office_id` AS `office_id`,
    src.`client_id` AS `client_id`,
    src.`currency_code` AS `currency_code`,
    src.`transaction_type_enum` AS `transaction_type_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_client_transaction AS src
WHERE src.`transaction_date` IS NOT NULL
  AND DATE(src.`transaction_date`) = CAST(@etl_date AS DATE)
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`transaction_date`),
    src.`office_id`,
    src.`client_id`,
    src.`currency_code`,
    src.`transaction_type_enum`;

DELETE FROM retail_banking_dm.dws_client_transaction_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_client_transaction_daily (
    `stat_date`, `office_id`, `client_id`, `currency_code`,
    `transaction_type_enum`, `record_count`, `total_amount`, `etl_time`
)
SELECT
    `stat_date`, `office_id`, `client_id`, `currency_code`,
    `transaction_type_enum`, `record_count`, `total_amount`, `etl_time`
FROM retail_banking_dm.stage_client_transaction_daily;
```

- [ ] **Step 2: Read the process table in the incremental ADS consumer**

Change the existing source relation and comment, preserving all target columns
and calculations:

```sql
FROM retail_banking_dm.stage_client_transaction_daily AS src
WHERE src.`stat_date` = CAST(@etl_date AS DATE);
```

- [ ] **Step 3: Apply the same Job I/O to the full-refresh variants**

The producer companion recreates the process table for the configured window,
then truncates and fills the managed DWS table from it:

```sql
DROP TABLE IF EXISTS retail_banking_dm.stage_client_transaction_daily;
CREATE TABLE retail_banking_dm.stage_client_transaction_daily AS
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`office_id` AS `office_id`,
    src.`client_id` AS `client_id`,
    src.`currency_code` AS `currency_code`,
    src.`transaction_type_enum` AS `transaction_type_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_client_transaction AS src
WHERE src.`transaction_date` IS NOT NULL
  AND DATE(src.`transaction_date`) >= CAST(@etl_start_date AS DATE)
  AND DATE(src.`transaction_date`) <= CAST(@etl_end_date AS DATE)
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`transaction_date`),
    src.`office_id`,
    src.`client_id`,
    src.`currency_code`,
    src.`transaction_type_enum`;

TRUNCATE TABLE retail_banking_dm.dws_client_transaction_daily;
INSERT INTO retail_banking_dm.dws_client_transaction_daily (
    `stat_date`, `office_id`, `client_id`, `currency_code`,
    `transaction_type_enum`, `record_count`, `total_amount`, `etl_time`
)
SELECT
    `stat_date`, `office_id`, `client_id`, `currency_code`,
    `transaction_type_enum`, `record_count`, `total_amount`, `etl_time`
FROM retail_banking_dm.stage_client_transaction_daily;
```

The ADS companion changes its source to the same stage table and retains the
existing date-window predicate.

- [ ] **Step 4: Run both scenario tests and companion equivalence**

Run:

```bash
make test PYTEST_ARGS='tests/lineage/test_cross_job_process_scenarios.py tests/lineage/test_sql_task_facts.py tests/lineage/test_lineage_output_metadata.py -q'
```

Expected: PASS for both projects, including retail banking base/companion I/O
equivalence.

- [ ] **Step 5: Commit the retail banking assets**

```bash
git add warehouses/retail_banking/mid/tasks/dws_client_transaction_daily.sql warehouses/retail_banking/ads/tasks/ads_customer_transaction_kpi_daily.sql warehouses/retail_banking/mid/tasks/full_refresh/dws_client_transaction_daily_full_refresh.sql warehouses/retail_banking/ads/tasks/full_refresh/ads_customer_transaction_kpi_daily_full_refresh.sql
git commit -m "feat(retail-banking): hand off customer metrics through process table"
```

### Task 4: Generate and strictly validate both projects

**Files:**
- Generate locally: `warehouses/shop/artifacts/lineage/lineage_data.json`
- Generate locally: `warehouses/shop/artifacts/lineage/job_dag.json`
- Generate locally: `warehouses/retail_banking/artifacts/lineage/lineage_data.json`
- Generate locally: `warehouses/retail_banking/artifacts/lineage/job_dag.json`
- Generate locally: both projects' lineage HTML outputs
- Do not force-add generated artifacts.

- [ ] **Step 1: Generate shop without cache and build its public DAG**

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.execution.task_run --project shop --refresh-dag --validate-only
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.refresh_lineage_html --project shop
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.lineage_cli validate --project shop
```

Expected: all commands exit 0; the process dataset has one producer and the
shop DAG contains `dws_store_sales_daily -> dim_store_metric_snapshot` with
`shop_dm.stage_store_sales_daily` evidence.

- [ ] **Step 2: Generate retail banking without cache and build its public DAG**

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.execution.task_run --project retail_banking --refresh-dag --validate-only
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.refresh_lineage_html --project retail_banking
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.lineage_cli validate --project retail_banking
```

Expected: all commands exit 0; the retail process dataset has one producer and
the DAG contains
`dws_client_transaction_daily -> ads_customer_transaction_kpi_daily` with
`retail_banking_dm.stage_client_transaction_daily` evidence.

`task_run --refresh-dag` is the no-cache generation entrypoint: it invokes the
extractor with `--no-cache`, writes fresh lineage, and derives the saved DAG
from that exact v2 payload before validating the execution plan.

- [ ] **Step 3: Audit evidence and field paths through existing readers**

Run the scenario test against the generated source assets:

```bash
make test PYTEST_ARGS='tests/lineage/test_cross_job_process_scenarios.py -q'
```

Also run CLI column queries and retain their JSON output in the task report:

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.lineage_cli column --project shop --table dim_store_metric_snapshot --column store_order_count --direction upstream --depth 4 --format json
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.lineage.lineage_cli column --project retail_banking --table ads_customer_transaction_kpi_daily --column total_amount --direction upstream --depth 4 --format json
```

Expected: each result contains its process-table column and its DWD upstream
column, with producer and consumer Job steps.

### Task 5: Full verification and redundancy-focused Code Review

**Files:**
- Review: all changes from `6b483372` through the implementation HEAD.
- Modify: only files required to fix confirmed review findings.

- [ ] **Step 1: Run focused lineage and execution regression tests**

```bash
make test PYTEST_ARGS='tests/lineage tests/test_task_run.py tests/test_execution_run_lock.py tests/test_execution_planner.py tests/test_process_table_assets.py -q -m "not api"'
```

Expected: PASS.

- [ ] **Step 2: Run the complete non-API gate**

```bash
make test
```

Expected: Ruff and format checks pass; all non-API tests pass.

- [ ] **Step 3: Request a dedicated whole-change Code Review**

Use `superpowers:requesting-code-review` with the fixed Git range. The reviewer
must inspect correctness and specifically answer:

1. Did the implementation add any producer resolution, identifier matching,
   graph traversal, or strict validation logic that already exists elsewhere?
2. Is the new acceptance test located at the correct lineage integration
   boundary, or does it duplicate lower-level unit tests?
3. Are project-specific concerns confined to warehouse SQL/test scenario data,
   without conditionals in core lineage code?
4. Do base/full-refresh variants have equivalent inputs and outputs?
5. Are process tables correctly absent from managed DDL/models?
6. Are existing managed targets, grains, slice predicates, and calculations
   preserved?

Findings must cite exact files and lines and be categorized as
Critical/Important/Minor.

- [ ] **Step 4: Fix every confirmed finding with RED/GREEN evidence**

For each accepted finding:

1. add a failing regression in the owning existing or scenario test module;
2. run it through `make test PYTEST_ARGS=...` and record the failure;
3. apply the smallest fix at the owning boundary;
4. rerun the focused and full gates;
5. re-run no-cache generation and strict validation for both projects.

Do not add a new shared helper solely to shorten a two-line test assertion. Do
not move project-specific SQL semantics into `src/dw_refactor_agent/lineage/`.

- [ ] **Step 5: Commit review fixes, if any**

```bash
git add tests warehouses/shop/mid/tasks warehouses/retail_banking/mid/tasks warehouses/retail_banking/ads/tasks src/dw_refactor_agent/lineage
git commit -m "fix(lineage): address process scenario review findings"
```

Skip this commit if the review is clean and there are no tracked fixes.

- [ ] **Step 6: Report final evidence**

Report:

- process table names and `dataset_type`;
- producer/consumer Job names and Job I/O;
- exact DAG dependency evidence;
- exact field paths and Job steps;
- diagnostics counts;
- strict validation results;
- focused/full test results;
- Code Review findings, fixes, and final verdict;
- confirmation that no redundant core lineage implementation was added.
