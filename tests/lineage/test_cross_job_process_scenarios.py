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
from tests.case_matrix import case_matrix


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


@case_matrix(
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
