import config
from refact.verification_plan import build_verification_plan


def test_build_verification_plan_uses_current_ddl_and_jobs(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks").mkdir()
    (project_dir / "ddl" / "dws_order.sql").write_text(
        "CREATE TABLE demo_dm.dws_order (order_id BIGINT) ENGINE=OLAP;",
        encoding="utf-8",
    )
    (project_dir / "models" / "dws_order.yaml").write_text(
        "version: 2\nname: dws_order\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "tasks" / "dws_order.sql").write_text(
        "INSERT INTO demo_dm.dws_order SELECT @etl_date;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo",
            "db": "demo_dm",
            "qa_db": "demo_dm_qa",
            "catalog": "internal",
        },
    )
    config._model_metadata_cache.clear()

    plan = build_verification_plan(
        "demo",
        {
            "affected_scope": {
                "assessment_tables": ["dws_order"],
                "assessment_tasks": ["dws_order"],
                "anchor_tables": ["dws_order"],
            }
        },
    )

    assert plan["project"] == "demo"
    assert plan["project_db"] == "demo_dm"
    assert plan["qa_db"] == "demo_dm_qa"
    assert list(plan["baseline_ddl"]) == ["dws_order"]
    assert plan["jobs_to_run"] == [
        {
            "job": "dws_order",
            "file": "demo/tasks/dws_order.sql",
            "layer": "DWS",
            "target": "dws_order",
            "needs_etl_date": True,
        }
    ]
    assert plan["checks"] == [
        {"table": "dws_order", "method": "count"},
        {"table": "dws_order", "method": "row_compare"},
    ]

    config._model_metadata_cache.clear()
