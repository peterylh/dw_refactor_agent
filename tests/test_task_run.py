import importlib.util
import subprocess
from pathlib import Path

import config

MODULE_PATH = Path(__file__).resolve().parent.parent / "exec" / "task_run.py"
SPEC = importlib.util.spec_from_file_location("task_run_module", MODULE_PATH)
task_run = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(task_run)


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

    assert task_run._is_partitioned_table("shop_dm", "ads_sales_dashboard", ["mysql"]) is True
    assert task_run._is_partitioned_table("shop_dm", "ads_sales_dashboard", ["mysql"]) is True
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

    task_run._ensure_partition("shop_dm", "ads_sales_dashboard", "2025-01-01", ["mysql"])

    assert calls == ["SHOW CREATE TABLE shop_dm.ads_sales_dashboard;"]


def test_ensure_full_refresh_partitions_skips_non_partitioned_table(monkeypatch):
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


def test_load_schema_reads_table_model_files(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project"
    models_dir = project_dir / "models"
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
        "version: 2\n"
        "layer: ADS\n"
        "config:\n"
        "  materialized: full\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(task_run, "_root", tmp_path)
    monkeypatch.setitem(task_run.PROJECT_CONFIG, "demo", {"dir": "demo_project"})
    task_run._SCHEMA_CONFIG_CACHE.clear()

    assert task_run._load_schema("demo") == {
        "dwd_customer": "snapshot",
        "ads_sales_dashboard": "full",
    }


def test_load_schema_cache_is_scoped_by_project(monkeypatch, tmp_path):
    for project, materialized in (("shop_like", "snapshot"), ("finance_like", "full")):
        models_dir = tmp_path / project / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "same_name.yaml").write_text(
            "version: 2\n"
            "name: same_name\n"
            "config:\n"
            f"  materialized: {materialized}\n",
            encoding="utf-8",
        )
        monkeypatch.setitem(task_run.PROJECT_CONFIG, project, {"dir": project})

    monkeypatch.setattr(task_run, "_root", tmp_path)
    task_run._SCHEMA_CONFIG_CACHE.clear()

    assert task_run._load_schema("shop_like") == {"same_name": "snapshot"}
    assert task_run._load_schema("finance_like") == {"same_name": "full"}


def test_discover_ods_dates_uses_model_layer(monkeypatch, tmp_path):
    models_dir = tmp_path / "demo_project" / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "source_events.yaml").write_text(
        "version: 2\n"
        "name: source_events\n"
        "layer: ODS\n",
        encoding="utf-8",
    )
    (models_dir / "ods_legacy.yaml").write_text(
        "version: 2\n"
        "name: ods_legacy\n"
        "layer: DWD\n",
        encoding="utf-8",
    )

    calls = []

    def fake_run(*args, **kwargs):
        sql = kwargs.get("input", "")
        calls.append(sql)
        if sql == "SHOW TABLES":
            return _completed(
                stdout=(
                    "Tables_in_demo_db\n"
                    "source_events\n"
                    "ods_legacy\n"
                )
            )
        return _completed(stdout="d\n2025-01-02\n2025-01-01\n")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(task_run.PROJECT_CONFIG, "demo", {"dir": "demo_project"})
    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    config._model_metadata_cache.clear()

    assert task_run._discover_ods_dates("demo", "demo_db", ["mysql"]) == [
        "2025-01-01",
        "2025-01-02",
    ]
    assert calls == [
        "SHOW TABLES",
        "SELECT DISTINCT DATE(load_time) AS d FROM demo_db.source_events ORDER BY d",
    ]
    config._model_metadata_cache.clear()


def test_build_job_dag_accepts_structured_lineage_edges(monkeypatch, tmp_path):
    lineage_dir = tmp_path / "lineage"
    lineage_dir.mkdir()
    (lineage_dir / "lineage_data_demo.json").write_text(
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
    monkeypatch.setattr(task_run, "_root", tmp_path)

    dag = task_run._build_job_dag("demo")

    assert dag._deps == {
        "ods_order": {"dwd_order_detail"},
        "dwd_order_detail": {"dws_order_summary"},
    }


def test_dag_needs_refresh_when_loaded_targets_do_not_match_tasks():
    dag = task_run.JobDAG([
        {"source": "M_SHOP_04_ORDER_DI", "target": "I_SHOP_CATG_SALE_MS"},
        {"source": "M_SHOP_04_ORDER_DI", "target": "I_SHOP_STORE_SALE_DS"},
    ])

    assert task_run._dag_needs_refresh_for_tasks(
        dag,
        {"dwd_order_detail", "dws_store_sales_daily"},
    ) is True


def test_dag_needs_refresh_keeps_current_dag_with_matching_targets():
    dag = task_run.JobDAG([
        {"source": "ods_order", "target": "dwd_order_detail"},
        {"source": "dwd_order_detail", "target": "dws_store_sales_daily"},
    ])

    assert task_run._dag_needs_refresh_for_tasks(
        dag,
        {"dwd_order_detail", "dws_store_sales_daily"},
    ) is False
