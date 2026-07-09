import json
import os
import subprocess

import dw_refactor_agent.config as config
from dw_refactor_agent.execution import task_run
from dw_refactor_agent.execution.planner import ExecutionPlanner


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["mysql"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_is_partitioned_table_uses_show_create_cache(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        return _completed(
            stdout=(
                "Table\tCreate Table\n"
                "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                "  `stat_date` date NOT NULL\n"
                ") ENGINE=OLAP\n"
                "PARTITION BY RANGE(`stat_date`) ()\n"
                "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1"
            )
        )

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()

    assert (
        task_run._is_partitioned_table(
            "shop_dm", "ads_sales_dashboard", ["mysql"]
        )
        is True
    )
    assert (
        task_run._is_partitioned_table(
            "shop_dm", "ads_sales_dashboard", ["mysql"]
        )
        is True
    )
    assert calls == ["SHOW CREATE TABLE shop_dm.ads_sales_dashboard;"]


def test_ensure_partition_skips_non_partitioned_table(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        return _completed(
            stdout=(
                "Table\tCreate Table\n"
                "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                "  `stat_date` date NOT NULL\n"
                ") ENGINE=OLAP\n"
                "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1"
            )
        )

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()
    task_run._TABLE_PARTITION_UNITS = {}

    task_run._ensure_partition(
        "shop_dm", "ads_sales_dashboard", "2025-01-01", ["mysql"]
    )

    assert calls == ["SHOW CREATE TABLE shop_dm.ads_sales_dashboard;"]


def test_ensure_partition_keeps_static_partition_table_static(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        if input.strip().startswith("SHOW CREATE TABLE"):
            return _completed(
                stdout=(
                    "Table\tCreate Table\n"
                    "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                    "  `stat_date` date NOT NULL\n"
                    ") ENGINE=OLAP\n"
                    "PARTITION BY RANGE(`stat_date`) (\n"
                    "  PARTITION p20250101 VALUES LESS THAN "
                    '("2025-01-02")\n'
                    ")\n"
                    "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1\n"
                    'PROPERTIES ("replication_num" = "1")'
                )
            )
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()
    task_run._TABLE_PARTITION_UNITS = {}

    task_run._ensure_partition(
        "shop_dm", "ads_sales_dashboard", "2025-01-01", ["mysql"]
    )

    assert calls == [
        "SHOW CREATE TABLE shop_dm.ads_sales_dashboard;",
        "ALTER TABLE shop_dm.ads_sales_dashboard DROP PARTITION IF EXISTS p20250101;",
        'ALTER TABLE shop_dm.ads_sales_dashboard ADD PARTITION p20250101 VALUES LESS THAN ("2025-01-02");',
    ]


def test_ensure_partition_toggles_dynamic_partition_table(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        if input.strip().startswith("SHOW CREATE TABLE"):
            return _completed(
                stdout=(
                    "Table\tCreate Table\n"
                    "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                    "  `stat_date` date NOT NULL\n"
                    ") ENGINE=OLAP\n"
                    "PARTITION BY RANGE(`stat_date`) ()\n"
                    "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1\n"
                    "PROPERTIES (\n"
                    '  "replication_num" = "1",\n'
                    '  "dynamic_partition.enable" = "true"\n'
                    ")"
                )
            )
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()
    task_run._TABLE_PARTITION_UNITS = {}

    task_run._ensure_partition(
        "shop_dm", "ads_sales_dashboard", "2025-01-01", ["mysql"]
    )

    assert calls == [
        "SHOW CREATE TABLE shop_dm.ads_sales_dashboard;",
        "ALTER TABLE shop_dm.ads_sales_dashboard SET ('dynamic_partition.enable' = 'false');",
        "ALTER TABLE shop_dm.ads_sales_dashboard DROP PARTITION IF EXISTS p20250101;",
        'ALTER TABLE shop_dm.ads_sales_dashboard ADD PARTITION p20250101 VALUES LESS THAN ("2025-01-02");',
        "ALTER TABLE shop_dm.ads_sales_dashboard SET ('dynamic_partition.enable' = 'true');",
    ]


def test_ensure_full_refresh_partitions_skips_non_partitioned_table(
    monkeypatch,
):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        return _completed(
            stdout=(
                "Table\tCreate Table\n"
                "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                "  `stat_date` date NOT NULL\n"
                ") ENGINE=OLAP\n"
                "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1"
            )
        )

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()

    task_run._ensure_full_refresh_partitions(
        "shop_dm",
        "ads_sales_dashboard",
        ["2025-01-01"],
        ["mysql"],
    )

    assert calls == ["SHOW CREATE TABLE shop_dm.ads_sales_dashboard;"]


def test_ensure_full_refresh_partitions_keeps_static_table_static(
    monkeypatch,
):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        if input.strip().startswith("SHOW CREATE TABLE"):
            return _completed(
                stdout=(
                    "Table\tCreate Table\n"
                    "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                    "  `stat_date` date NOT NULL\n"
                    ") ENGINE=OLAP\n"
                    "PARTITION BY RANGE(`stat_date`) (\n"
                    "  PARTITION p20250101 VALUES LESS THAN "
                    '("2025-01-02")\n'
                    ")\n"
                    "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1\n"
                    'PROPERTIES ("replication_num" = "1")'
                )
            )
        if input.strip().startswith("SHOW PARTITIONS"):
            return _completed(
                stdout="PartitionId\tPartitionName\n1\tp20250101\n"
            )
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()

    task_run._ensure_full_refresh_partitions(
        "shop_dm",
        "ads_sales_dashboard",
        ["2025-01-01"],
        ["mysql"],
    )

    assert all("dynamic_partition.enable" not in call for call in calls)
    assert any(
        call
        == (
            "ALTER TABLE shop_dm.ads_sales_dashboard "
            "DROP PARTITION IF EXISTS p20250101;"
        )
        for call in calls
    )
    assert any(
        call.startswith(
            "ALTER TABLE shop_dm.ads_sales_dashboard "
            "ADD PARTITION p_full VALUES LESS THAN"
        )
        for call in calls
    )


def _write_execution_project(
    monkeypatch,
    tmp_path,
    *,
    job_name="dwd_customer",
    model_config="execution:\n  materialized: incremental\n",
    companion=False,
):
    project_dir = tmp_path / "demo_project"
    task_dir = project_dir / "mid" / "tasks"
    model_dir = project_dir / "mid" / "models"
    ddl_dir = project_dir / "mid" / "ddl"
    task_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    ddl_dir.mkdir(parents=True)
    sql_file = task_dir / f"{job_name}.sql"
    sql_file.write_text("SELECT @etl_date, @full_refresh;", encoding="utf-8")
    (model_dir / f"{job_name}.yaml").write_text(
        f"version: 2\nname: {job_name}\nlayer: DWD\n{model_config}",
        encoding="utf-8",
    )
    (ddl_dir / f"{job_name}.sql").write_text(
        "CREATE TABLE demo_db.dwd_customer (\n"
        "  id BIGINT,\n"
        "  stat_date DATE\n"
        ") ENGINE=OLAP DISTRIBUTED BY HASH(id) BUCKETS 1;",
        encoding="utf-8",
    )
    if companion:
        companion_dir = task_dir / "full_refresh"
        companion_dir.mkdir()
        (companion_dir / f"{job_name}_full_refresh.sql").write_text(
            "SELECT @full_refresh;",
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "execution": {
                "default_slice": {
                    "param": "etl_date",
                    "column": "stat_date",
                    "period": "D",
                }
            },
        },
    )
    return sql_file


def test_incremental_full_refresh_replays_slices_with_full_refresh_zero(
    monkeypatch,
    tmp_path,
):
    calls = []
    ensured = []
    sql_file = _write_execution_project(monkeypatch, tmp_path)
    planner = ExecutionPlanner("demo")

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("input", "").strip())
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    monkeypatch.setattr(
        task_run,
        "_ensure_partition",
        lambda db, table, etl_date, mysql_cmd: ensured.append(
            (db, table, etl_date)
        ),
    )

    task_run._run_job_full_refresh(
        "dwd_customer",
        sql_file,
        ["mysql"],
        "demo_db",
        planner,
        ["2025-01-01", "2025-01-02"],
    )

    assert ensured == [
        ("demo_db", "dwd_customer", "2025-01-01"),
        ("demo_db", "dwd_customer", "2025-01-02"),
    ]
    assert len(calls) == 2
    assert calls[0].startswith(
        "SET @etl_date = '2025-01-01';\nSET @full_refresh = 0;"
    )
    assert calls[1].startswith(
        "SET @etl_date = '2025-01-02';\nSET @full_refresh = 0;"
    )


def test_companion_full_refresh_runs_companion_with_full_refresh_one(
    monkeypatch,
    tmp_path,
):
    calls = []
    full_partitions = []
    sql_file = _write_execution_project(
        monkeypatch,
        tmp_path,
        model_config=(
            "execution:\n"
            "  materialized: incremental\n"
            "  full_refresh_strategy: companion\n"
        ),
        companion=True,
    )
    planner = ExecutionPlanner("demo")

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("input", "").strip())
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    monkeypatch.setattr(
        task_run,
        "_ensure_full_refresh_partitions",
        lambda db, table, dates, mysql_cmd: full_partitions.append(
            (db, table, dates)
        ),
    )

    task_run._run_job_full_refresh(
        "dwd_customer",
        sql_file,
        ["mysql"],
        "demo_db",
        planner,
        ["2025-01-01", "2025-01-02"],
    )

    assert full_partitions == [
        ("demo_db", "dwd_customer", ["2025-01-01", "2025-01-02"])
    ]
    assert len(calls) == 1
    assert calls[0].startswith("SET @full_refresh = 1;\n")
    assert "SELECT @full_refresh;" in calls[0]


def test_build_job_dag_refreshes_lineage_with_src_pythonpath(
    monkeypatch, tmp_path
):
    lineage_path = tmp_path / "lineage_data.json"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        lineage_path.write_text(
            json.dumps({"tables": [], "edges": []}),
            encoding="utf-8",
        )
        return _completed()

    monkeypatch.setattr(
        task_run, "_resolve_lineage_data_file", lambda _: lineage_path
    )
    monkeypatch.setattr(task_run.subprocess, "run", fake_run)

    dag = task_run._build_job_dag("shop")

    assert dag._edges == []
    cmd, kwargs = calls[0]
    assert cmd[:3] == [
        os.sys.executable,
        "-m",
        "dw_refactor_agent.lineage.lineage_extractor",
    ]
    assert str(config.SRC_ROOT) in kwargs["env"]["PYTHONPATH"].split(
        os.pathsep
    )


def test_get_task_files_reads_mid_and_ads_task_dirs(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / "full_refresh").mkdir(parents=True)
    (project_dir / "ads" / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / "legacy_job.sql").write_text(
        "",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dwd_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    (
        project_dir
        / "mid"
        / "tasks"
        / "full_refresh"
        / "dwd_customer_full_refresh.sql"
    ).write_text("", encoding="utf-8")
    (project_dir / "ads" / "tasks" / "ads_customer.sql").write_text(
        "",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_db",
        },
    )

    task_files = task_run._get_task_files("demo")

    assert sorted(task_files) == [
        "ads_customer",
        "dwd_customer",
    ]
    assert task_files["dwd_customer"] == (
        project_dir / "mid" / "tasks" / "dwd_customer.sql"
    )


def test_load_partition_units_reads_catalog_database_ods_ddl(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    ddl_dir = project_dir / "mid" / "ddl"
    ods_ddl_dir = project_dir / "ods" / "ddl" / "internal" / "demo_db"
    ddl_dir.mkdir(parents=True)
    ods_ddl_dir.mkdir(parents=True)
    (ddl_dir / "dwd_customer.sql").write_text(
        "CREATE TABLE demo_db.dwd_customer (id BIGINT)\n"
        'PROPERTIES ("dynamic_partition.time_unit" = "MONTH");',
        encoding="utf-8",
    )
    (ods_ddl_dir / "ods_customer.sql").write_text(
        "CREATE TABLE demo_db.ods_customer (id BIGINT)\n"
        'PROPERTIES ("dynamic_partition.time_unit" = "DAY");',
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_db",
        },
    )
    config.clear_model_metadata_cache()

    assert task_run._load_partition_units("demo") == {
        "dwd_customer": "MONTH",
        "ods_customer": "DAY",
    }
    config.clear_model_metadata_cache()


def test_load_partition_units_uses_model_execution_slice_period(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    task_dir = project_dir / "mid" / "tasks"
    ddl_dir = project_dir / "mid" / "ddl"
    model_dir = project_dir / "mid" / "models"
    task_dir.mkdir(parents=True)
    ddl_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    (task_dir / "dws_monthly.sql").write_text("SELECT 1;", encoding="utf-8")
    (ddl_dir / "dws_monthly.sql").write_text(
        "CREATE TABLE demo_db.dws_monthly (\n"
        "  id BIGINT,\n"
        "  stat_month_date DATE\n"
        ") ENGINE=OLAP\n"
        "PARTITION BY RANGE(stat_month_date) (\n"
        '  PARTITION p202406 VALUES LESS THAN ("2024-07-01")\n'
        ");",
        encoding="utf-8",
    )
    (model_dir / "dws_monthly.yaml").write_text(
        "version: 2\n"
        "name: dws_monthly\n"
        "layer: DWS\n"
        "execution:\n"
        "  materialized: incremental\n"
        "  slice:\n"
        "    param: etl_date\n"
        "    column: stat_month_date\n"
        "    period: M\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_db",
        },
    )
    config.clear_model_metadata_cache()

    assert task_run._load_partition_units("demo") == {"dws_monthly": "MONTH"}
    config.clear_model_metadata_cache()


def test_load_partition_units_does_not_validate_unrelated_strategies(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    task_dir = project_dir / "mid" / "tasks"
    model_dir = project_dir / "mid" / "models"
    ddl_dir = project_dir / "mid" / "ddl"
    task_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    ddl_dir.mkdir(parents=True)
    (task_dir / "dwd_orders.sql").write_text("SELECT 1;", encoding="utf-8")
    (task_dir / "bad_companion.sql").write_text("SELECT 1;", encoding="utf-8")
    (ddl_dir / "dwd_orders.sql").write_text(
        'CREATE TABLE demo_db.dwd_orders (stat_date DATE) PROPERTIES ("dynamic_partition.time_unit" = "MONTH");',
        encoding="utf-8",
    )
    (model_dir / "bad_companion.yaml").write_text(
        "version: 2\n"
        "name: bad_companion\n"
        "layer: DWD\n"
        "execution:\n"
        "  materialized: incremental\n"
        "  full_refresh_strategy: companion\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
            "catalog": "internal",
            "db": "demo_db",
            "execution": {
                "default_slice": {
                    "param": "etl_date",
                    "column": "stat_date",
                    "period": "D",
                }
            },
        },
    )
    config.clear_model_metadata_cache()

    assert task_run._load_partition_units("demo") == {
        "bad_companion": "DAY",
        "dwd_orders": "DAY",
    }
    config.clear_model_metadata_cache()


def test_discover_ods_dates_uses_model_layer(monkeypatch, tmp_path):
    models_dir = tmp_path / "demo_project" / "mid" / "models"
    ods_models_dir = (
        tmp_path / "demo_project" / "ods" / "models" / "internal" / "demo_db"
    )
    models_dir.mkdir(parents=True)
    ods_models_dir.mkdir(parents=True)
    (ods_models_dir / "source_events.yaml").write_text(
        "version: 2\nname: source_events\nlayer: ODS\n",
        encoding="utf-8",
    )
    (models_dir / "ods_legacy.yaml").write_text(
        "version: 2\nname: ods_legacy\nlayer: DWD\n",
        encoding="utf-8",
    )

    calls = []

    def fake_run(*args, **kwargs):
        sql = kwargs.get("input", "")
        calls.append(sql)
        if sql == "SHOW TABLES":
            return _completed(
                stdout=("Tables_in_demo_db\nsource_events\nods_legacy\n")
            )
        return _completed(stdout="d\n2025-01-02\n2025-01-01\n")

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG, "demo", {"dir": "demo_project"}
    )
    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    config.clear_model_metadata_cache()

    assert task_run._discover_ods_dates("demo", "demo_db", ["mysql"]) == [
        "2025-01-01",
        "2025-01-02",
    ]
    assert calls == [
        "SHOW TABLES",
        "SELECT DISTINCT DATE(load_time) AS d FROM demo_db.source_events ORDER BY d",
    ]
    config.clear_model_metadata_cache()


def test_resolve_full_refresh_dates_prefers_explicit_dates(monkeypatch):
    def fail_discover(*args, **kwargs):
        raise AssertionError("should not discover ODS dates")

    monkeypatch.setattr(task_run, "_discover_ods_dates", fail_discover)

    assert task_run._resolve_full_refresh_dates(
        "demo",
        "demo_db",
        ["mysql"],
        ["2025-01-02", "2025-01-01", "2025-01-02"],
    ) == ["2025-01-02", "2025-01-01"]


def test_build_job_dag_accepts_structured_lineage_edges(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    lineage_dir = project_dir / "artifacts" / "lineage"
    lineage_dir.mkdir(parents=True)
    (lineage_dir / "lineage_data.json").write_text(
        """
        {
          "edges": [
            {
              "source": {"type": "column", "id": "ods_order.order_id"},
              "target": {"type": "column", "id": "dwd_order_detail.order_id"}
            },
            {
              "source": {"type": "column", "id": "dwd_order_detail.order_id"},
              "target": {"type": "table", "id": "dws_order_summary"},
              "relation_type": "filter"
            },
            {
              "source": {"type": "literal", "value": "1"},
              "target": {"type": "column", "id": "dwd_order_detail.flag"}
            },
            {
              "source": {"type": "column", "id": "dwd_order_detail.order_id"},
              "target": {"type": "column", "id": "dwd_order_detail.order_id"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    dag = task_run._build_job_dag("demo")

    assert dag._deps == {
        "ods_order": {"dwd_order_detail"},
        "dwd_order_detail": {"dws_order_summary"},
    }


def test_task_run_resolvers_ignore_old_lineage_artifact_paths(
    monkeypatch, tmp_path
):
    project_dir = tmp_path / "demo_project"
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    old_lineage_dir = tmp_path / "lineage"
    old_lineage_dir.mkdir()
    (old_lineage_dir / "lineage_data_demo.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (old_lineage_dir / "job_dag_demo.json").write_text(
        "{}",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    assert task_run._resolve_lineage_data_file("demo") == (
        project_dir / "artifacts" / "lineage" / "lineage_data.json"
    )
    assert task_run._resolve_job_dag_file("demo") == (
        project_dir / "artifacts" / "lineage" / "job_dag.json"
    )


def test_build_job_dag_collapses_transient_tables(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    lineage_dir = project_dir / "artifacts" / "lineage"
    lineage_dir.mkdir(parents=True)
    (lineage_dir / "lineage_data.json").write_text(
        """
        {
          "tables": [
            {"name": "dwd_orders", "layer": "DWD", "columns": []},
            {"name": "tmp_orders_stage", "layer": "OTHER", "columns": [], "is_transient": true},
            {"name": "dws_orders", "layer": "DWS", "columns": []}
          ],
          "edges": [
            {
              "source": {"type": "column", "id": "dwd_orders.order_id"},
              "target": {"type": "column", "id": "tmp_orders_stage.order_id"}
            },
            {
              "source": {"type": "column", "id": "tmp_orders_stage.order_id"},
              "target": {"type": "column", "id": "dws_orders.order_id"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    dag = task_run._build_job_dag("demo")

    assert dag._deps == {"dwd_orders": {"dws_orders"}}
    assert "tmp_orders_stage" not in dag._deps
    assert "tmp_orders_stage" not in dag._rev


def test_dag_needs_refresh_when_loaded_targets_do_not_match_tasks():
    dag = task_run.JobDAG(
        [
            {"source": "M_SHOP_04_ORDER_DI", "target": "I_SHOP_CATG_SALE_MS"},
            {"source": "M_SHOP_04_ORDER_DI", "target": "I_SHOP_STORE_SALE_DS"},
        ]
    )

    assert (
        task_run._dag_needs_refresh_for_tasks(
            dag,
            {"dwd_order_detail", "dws_store_sales_daily"},
        )
        is True
    )


def test_dag_needs_refresh_keeps_current_dag_with_matching_targets():
    dag = task_run.JobDAG(
        [
            {"source": "ods_order", "target": "dwd_order_detail"},
            {"source": "dwd_order_detail", "target": "dws_store_sales_daily"},
        ]
    )

    assert (
        task_run._dag_needs_refresh_for_tasks(
            dag,
            {"dwd_order_detail", "dws_store_sales_daily"},
        )
        is False
    )
