import config
from refact.incremental_lineage import build_lineage_artifacts


def _write_demo_project(root):
    project_dir = root / "demo"
    ods_ddl_dir = project_dir / "ods" / "ddl" / "internal" / "demo_dm"
    ods_model_dir = project_dir / "ods" / "models" / "internal" / "demo_dm"
    mid_ddl_dir = project_dir / "mid" / "ddl"
    mid_model_dir = project_dir / "mid" / "models"
    mid_tasks_dir = project_dir / "mid" / "tasks"
    ods_ddl_dir.mkdir(parents=True)
    ods_model_dir.mkdir(parents=True)
    mid_ddl_dir.mkdir(parents=True)
    mid_model_dir.mkdir()
    mid_tasks_dir.mkdir()
    (ods_ddl_dir / "ods_order.sql").write_text(
        """
CREATE TABLE demo_dm.ods_order (
  order_id BIGINT,
  amount DECIMAL(10,2)
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 1
PROPERTIES ("replication_num" = "1");
""",
        encoding="utf-8",
    )
    (mid_ddl_dir / "dwd_order.sql").write_text(
        """
CREATE TABLE demo_dm.dwd_order (
  order_id BIGINT,
  amount DECIMAL(10,2)
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 1
PROPERTIES ("replication_num" = "1");
""",
        encoding="utf-8",
    )
    (ods_model_dir / "ods_order.yaml").write_text(
        "version: 2\nname: ods_order\nlayer: ODS\n",
        encoding="utf-8",
    )
    (mid_model_dir / "dwd_order.yaml").write_text(
        "version: 2\nname: dwd_order\nlayer: DWD\n",
        encoding="utf-8",
    )
    (mid_tasks_dir / "dwd_order.sql").write_text(
        """
INSERT INTO demo_dm.dwd_order (order_id, amount)
SELECT order_id, amount
FROM demo_dm.ods_order;
""",
        encoding="utf-8",
    )


def test_build_lineage_artifacts_reuses_valid_task_cache(
    tmp_path, monkeypatch
):
    _write_demo_project(tmp_path)
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {"dir": "demo", "catalog": "internal", "db": "demo_dm"},
    )
    config.clear_model_metadata_cache()

    output_path = tmp_path / "lineage_data_demo.json"
    cache_path = tmp_path / "task_lineage_cache.json"

    first = build_lineage_artifacts("demo", output_path, cache_path)
    second = build_lineage_artifacts(
        "demo",
        output_path,
        cache_path,
        previous_cache_path=cache_path,
    )

    assert first["summary"]["computed_task_count"] == 1
    assert first["summary"]["reused_task_count"] == 0
    assert second["summary"]["computed_task_count"] == 0
    assert second["summary"]["reused_task_count"] == 1
    assert second["cache"]["tasks"][0]["source_file"] == "dwd_order.sql"
    assert output_path.exists()
    assert cache_path.exists()

    ddl_path = (
        tmp_path
        / "demo"
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "ods_order.sql"
    )
    ddl_path.write_text(
        ddl_path.read_text(encoding="utf-8").replace(
            "amount DECIMAL(10,2)",
            "amount DECIMAL(12,2)",
        ),
        encoding="utf-8",
    )

    third = build_lineage_artifacts(
        "demo",
        output_path,
        cache_path,
        previous_cache_path=cache_path,
    )

    assert third["summary"]["computed_task_count"] == 1
    assert third["summary"]["reused_task_count"] == 0

    config.clear_model_metadata_cache()
