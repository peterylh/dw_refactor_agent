import re
from dataclasses import dataclass
from typing import Dict, Iterator, Sequence, Set, Tuple

import pytest

import dw_refactor_agent.lineage.lineage_extractor as lineage_extractor
from dw_refactor_agent.config import (
    project_dir as configured_project_dir,
)
from dw_refactor_agent.config import (
    task_source_file,
)
from dw_refactor_agent.execution.planner import ExecutionPlanner
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
    producer_path: str
    consumer_path: str
    producer_job: str
    consumer_job: str
    process_table: str
    upstream_column: str
    process_column: str
    target_table: str
    target_column: str
    companions: Tuple[str, ...] = ()


SCENARIOS = (
    Scenario(
        project="shop",
        producer_path="mid/tasks/dws_store_sales_daily.sql",
        consumer_path="mid/tasks/dim_store_metric_snapshot.sql",
        producer_job="dws_store_sales_daily",
        consumer_job="dim_store_metric_snapshot",
        process_table="shop_dm.stage_store_sales_daily",
        upstream_column="dwd_order_detail.order_id",
        process_column="stage_store_sales_daily.order_count",
        target_table="dim_store_metric_snapshot",
        target_column="store_order_count",
        companions=(
            "mid/tasks/full_refresh/dws_store_sales_daily_full_refresh.sql",
            (
                "mid/tasks/full_refresh/"
                "dim_store_metric_snapshot_full_refresh.sql"
            ),
        ),
    ),
    Scenario(
        project="retail_banking",
        producer_path="mid/tasks/dws_client_transaction_daily.sql",
        consumer_path=("ads/tasks/ads_customer_transaction_kpi_daily.sql"),
        producer_job="dws_client_transaction_daily",
        consumer_job="ads_customer_transaction_kpi_daily",
        process_table="retail_banking_dm.stage_client_transaction_daily",
        upstream_column="dwd_client_transaction.amount",
        process_column="stage_client_transaction_daily.total_amount",
        target_table="ads_customer_transaction_kpi_daily",
        target_column="total_amount",
        companions=(
            (
                "mid/tasks/full_refresh/"
                "dws_client_transaction_daily_full_refresh.sql"
            ),
            (
                "ads/tasks/full_refresh/"
                "ads_customer_transaction_kpi_daily_full_refresh.sql"
            ),
        ),
    ),
)


@pytest.fixture(autouse=True)
def restore_lineage_extractor_project() -> Iterator[None]:
    project_state = (
        lineage_extractor.CURRENT_PROJECT,
        lineage_extractor.CURRENT_CATALOG,
        lineage_extractor.CURRENT_DB,
    )
    try:
        yield
    finally:
        (
            lineage_extractor.CURRENT_PROJECT,
            lineage_extractor.CURRENT_CATALOG,
            lineage_extractor.CURRENT_DB,
        ) = project_state


def _extract_tasks(
    project: str,
    relative_paths: Sequence[str],
) -> Tuple[Dict, Dict]:
    configure_project(project)
    project_path = configured_project_dir(project)
    assert project_path is not None, "configured project directory is missing"

    task_paths = [
        project_path / relative_path for relative_path in relative_paths
    ]
    missing_paths = [path for path in task_paths if not path.is_file()]
    assert not missing_paths, (
        f"checked-in task files are missing: {missing_paths}"
    )

    schema = build_schema_from_project_ddl(project)
    result = extract_lineage_from_task_files(
        task_paths,
        tasks_dir=project_path,
        schema=schema,
        parallel=1,
        source_file_for_path=lambda path: task_source_file(project, path),
    )
    assert result["errors"] == []
    return result, schema


def _scenario_lineage(scenario: Scenario) -> Dict:
    result, schema = _extract_tasks(
        scenario.project,
        [scenario.producer_path, scenario.consumer_path],
    )
    data = build_lineage_output(
        result["lineage"],
        schema,
        task_results=result["task_results"],
    )
    validate_lineage_v2(data)
    return data


def _io_by_position(
    result: Dict,
) -> Tuple[Tuple[Set[str], Set[str]], ...]:
    return tuple(
        (set(task["input_tables"]), set(task["output_tables"]))
        for task in result["task_results"]
    )


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=lambda scenario: scenario.project,
)
def test_cross_job_process_scenario_is_queryable_and_schedulable(
    scenario: Scenario,
) -> None:
    data = _scenario_lineage(scenario)

    process_dataset = next(
        (
            table
            for table in data["tables"]
            if table["full_name"] == scenario.process_table
        ),
        None,
    )
    assert process_dataset is not None, (
        f"process dataset is missing: {scenario.process_table}"
    )
    assert process_dataset["dataset_type"] == "process"

    jobs = {job["name"]: job for job in data["jobs"]}
    assert scenario.process_table in jobs[scenario.producer_job]["outputs"]
    assert scenario.process_table in jobs[scenario.consumer_job]["inputs"]
    assert [
        diagnostic
        for diagnostic in data["diagnostics"]
        if diagnostic["dataset"] == scenario.process_table
    ] == []
    assert all("source_file" not in edge for edge in data["edges"])

    assert job_dag_from_lineage(data).data_dependencies == [
        {
            "upstream_job": scenario.producer_job,
            "downstream_job": scenario.consumer_job,
            "datasets": [scenario.process_table],
        }
    ]

    view = LineageView.from_data(scenario.project, data)
    target_column = f"{scenario.target_table}.{scenario.target_column}"
    matching_records = [
        record
        for record in view.column_lineage_for_table(scenario.target_table)
        if record["source"] == scenario.upstream_column
        and record["target"] == target_column
        and scenario.process_column in record.get("transient_path", [])
    ]
    assert len(matching_records) == 1
    assert {
        step["job"] for step in matching_records[0]["expression_chain"]
    } == {scenario.producer_job, scenario.consumer_job}

    target_lineage = build_column_lineage(
        view,
        scenario.target_table,
        scenario.target_column,
        direction="upstream",
        depth=4,
    )
    required_columns = {scenario.upstream_column, target_column}
    assert any(
        required_columns <= set(path.nodes) for path in target_lineage.paths
    )
    assert target_lineage.jobs == {
        scenario.producer_job,
        scenario.consumer_job,
    }


@pytest.mark.parametrize(
    "scenario",
    [scenario for scenario in SCENARIOS if scenario.companions],
    ids=lambda scenario: scenario.project,
)
def test_full_refresh_companions_preserve_base_task_io(
    scenario: Scenario,
) -> None:
    base_result, _schema = _extract_tasks(
        scenario.project,
        [scenario.producer_path, scenario.consumer_path],
    )
    companion_result, _schema = _extract_tasks(
        scenario.project,
        scenario.companions,
    )

    assert _io_by_position(companion_result) == _io_by_position(base_result)
    if scenario.project == "shop":
        for task_result in companion_result["task_results"]:
            condition_expressions = {
                entry.get("condition_expression", "")
                for entry in task_result["entries"]
                if entry["lineage_type"] == "indirect"
            }
            assert any(
                "@etl_start_date" in expression
                and "@etl_end_date" in expression
                for expression in condition_expressions
            )


@pytest.mark.parametrize(
    ("project", "relative_path", "process_table"),
    [
        (scenario.project, relative_path, scenario.process_table)
        for scenario in SCENARIOS
        for relative_path in (
            scenario.producer_path,
            scenario.companions[0],
        )
    ],
    ids=("shop-slice", "shop-window", "retail-slice", "retail-window"),
)
def test_process_producer_ctas_is_one_replica_and_immutable(
    project: str,
    relative_path: str,
    process_table: str,
) -> None:
    project_path = configured_project_dir(project)
    assert project_path is not None
    sql = (project_path / relative_path).read_text(encoding="utf-8")
    ctas = re.search(
        rf"CREATE\s+TABLE\s+{re.escape(process_table)}\s+"
        r'PROPERTIES\s*\(\s*"replication_num"\s*=\s*"1"\s*\)\s+AS\b',
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    assert ctas is not None
    assert not re.search(
        rf"\b(?:DELETE\s+FROM|UPDATE|TRUNCATE\s+TABLE|INSERT\s+INTO|"
        rf"ALTER\s+TABLE|DROP\s+TABLE(?:\s+IF\s+EXISTS)?)\s+"
        rf"{re.escape(process_table)}\b",
        sql[ctas.end() :],
        flags=re.IGNORECASE,
    )


@pytest.mark.parametrize(
    "relative_path",
    (SCENARIOS[0].producer_path, SCENARIOS[0].companions[0]),
    ids=("slice", "window"),
)
def test_shop_producer_folds_process_cleanup_into_ctas(
    relative_path: str,
) -> None:
    result, _schema = _extract_tasks("shop", [relative_path])
    entries = result["task_results"][0]["entries"]
    process_table = SCENARIOS[0].process_table.rsplit(".", 1)[-1]

    assert [
        entry
        for entry in entries
        if entry.get("source_table") == process_table
        and entry.get("target_table") == process_table
    ] == []
    assert any(
        entry.get("target_table") == process_table
        and entry.get("target_column") == "discount_amount"
        and entry.get("expression")
        == "COALESCE(SUM(discount), 0.00) AS discount_amount"
        for entry in entries
    )
    assert {
        entry["condition_expression"]
        for entry in entries
        if entry.get("target_table") == process_table
        and entry.get("condition_type") == "HAVING"
    } == {
        "COUNT(DISTINCT order_id) <> 0 AND "
        "(SUM(subtotal - discount) IS NULL OR "
        "SUM(subtotal - discount) >= 0)"
    }


def test_shop_full_refresh_uses_one_companion_invocation_per_job() -> None:
    scenario = next(
        scenario for scenario in SCENARIOS if scenario.project == "shop"
    )
    project_path = configured_project_dir(scenario.project)
    assert project_path is not None
    planner = ExecutionPlanner(scenario.project)

    invocations = []
    for job_name, relative_path in (
        (scenario.producer_job, scenario.producer_path),
        (scenario.consumer_job, scenario.consumer_path),
    ):
        spec = planner.task_spec(job_name, project_path / relative_path)
        invocations.extend(
            planner.plan_full_refresh(spec, ["2025-01-15", "2025-01-16"])
        )

    window = {
        "etl_start_date": "2025-01-15",
        "etl_end_date": "2025-01-16",
    }
    assert [
        (
            invocation.job_name,
            invocation.sql_path.relative_to(project_path).as_posix(),
            invocation.params,
            invocation.full_refresh,
            invocation.strategy,
        )
        for invocation in invocations
    ] == [
        (
            scenario.producer_job,
            scenario.companions[0],
            window,
            True,
            "companion",
        ),
        (
            scenario.consumer_job,
            scenario.companions[1],
            window,
            True,
            "companion",
        ),
    ]
