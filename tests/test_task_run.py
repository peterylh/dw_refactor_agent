import json
import os
import subprocess

import dw_refactor_agent.config as config
from dw_refactor_agent.execution import task_run


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


def test_snapshot_full_refresh_without_companion_keeps_static_table_static(
    monkeypatch,
    tmp_path,
):
    calls = []
    ensured = []
    sql_file = tmp_path / "dwd_customer.sql"
    sql_file.write_text("SELECT 1;", encoding="utf-8")

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("input", "").strip())
        return _completed()

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    monkeypatch.setattr(task_run, "_is_partitioned_table", lambda *args: True)
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
        "shop_dm",
        {"dwd_customer": "snapshot"},
        ["2025-01-01"],
    )

    assert all("dynamic_partition.enable" not in call for call in calls)
    assert (
        "ALTER TABLE shop_dm.dwd_customer DROP PARTITION IF EXISTS p_full;"
        in calls
    )
    assert ensured == [("shop_dm", "dwd_customer", "2025-01-01")]


def test_load_schema_reads_table_model_files(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "dwd_customer.yaml").write_text(
        "version: 2\n"
        "name: dwd_customer\n"
        "layer: DWD\n"
        "config:\n"
        "  materialized: snapshot\n",
        encoding="utf-8",
    )
    (models_dir / "ads_sales_dashboard.yaml").write_text(
        "version: 2\nlayer: ADS\nconfig:\n  materialized: full\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        task_run.PROJECT_CONFIG, "demo", {"dir": "demo_project"}
    )
    task_run._SCHEMA_CONFIG_CACHE.clear()
    config.clear_model_metadata_cache()

    assert task_run._load_schema("demo") == {
        "dwd_customer": "snapshot",
        "ads_sales_dashboard": "full",
    }
    config.clear_model_metadata_cache()


def test_load_schema_reads_catalog_database_ods_models(
    monkeypatch,
    tmp_path,
):
    project_dir = tmp_path / "demo_project"
    models_dir = project_dir / "mid" / "models"
    ods_models_dir = project_dir / "ods" / "models" / "internal" / "demo_db"
    models_dir.mkdir(parents=True)
    ods_models_dir.mkdir(parents=True)
    (models_dir / "dwd_customer.yaml").write_text(
        "version: 2\n"
        "name: dwd_customer\n"
        "layer: DWD\n"
        "config:\n"
        "  materialized: snapshot\n",
        encoding="utf-8",
    )
    (ods_models_dir / "ods_customer.yaml").write_text(
        "version: 2\n"
        "name: ods_customer\n"
        "layer: ODS\n"
        "config:\n"
        "  materialized: source\n",
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
    task_run._SCHEMA_CONFIG_CACHE.clear()
    config.clear_model_metadata_cache()

    assert task_run._load_schema("demo") == {
        "dwd_customer": "snapshot",
        "ods_customer": "source",
    }
    config.clear_model_metadata_cache()


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
    assert task_run._get_full_refresh_path(
        project_dir / "mid" / "tasks",
        "dwd_customer",
    ) == (
        project_dir
        / "mid"
        / "tasks"
        / "full_refresh"
        / "dwd_customer_full_refresh.sql"
    )


def test_load_schema_cache_is_scoped_by_project(monkeypatch, tmp_path):
    for project, materialized in (
        ("shop_like", "snapshot"),
        ("finance_like", "full"),
    ):
        models_dir = tmp_path / project / "mid" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "same_name.yaml").write_text(
            "version: 2\n"
            "name: same_name\n"
            "config:\n"
            f"  materialized: {materialized}\n",
            encoding="utf-8",
        )
        monkeypatch.setitem(task_run.PROJECT_CONFIG, project, {"dir": project})
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    task_run._SCHEMA_CONFIG_CACHE.clear()
    config.clear_model_metadata_cache()

    assert task_run._load_schema("shop_like") == {"same_name": "snapshot"}
    assert task_run._load_schema("finance_like") == {"same_name": "full"}
    config.clear_model_metadata_cache()


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

    assert task_run._load_partition_units("demo") == {
        "dwd_customer": "MONTH",
        "ods_customer": "DAY",
    }


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
