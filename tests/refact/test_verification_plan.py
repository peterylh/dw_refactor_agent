import ast
from pathlib import Path

import dw_refactor_agent.config as config
from dw_refactor_agent.refactor.verification_plan import (
    build_verification_plan,
    get_partition_col,
    load_baseline_ddl,
    parse_partition_col_from_ddl,
    strip_insert_data,
)


def test_verification_plan_uses_public_ddl_deriver_api():
    source_path = (
        Path(__file__).parents[2]
        / "src"
        / "dw_refactor_agent"
        / "refactor"
        / "verification_plan.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    private_imports = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "dw_refactor_agent.ddl_deriver.ddl_deriver":
            continue
        private_imports.extend(
            alias.name for alias in node.names if alias.name.startswith("_")
        )

    assert private_imports == []


def test_build_verification_plan_uses_baseline_ddl_changes_and_jobs(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "ddl" / "dws_order.sql").write_text(
        "CREATE TABLE demo_dm.dws_order (order_id BIGINT) ENGINE=OLAP;",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dws_order.yaml").write_text(
        "version: 2\nname: dws_order\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_order.sql").write_text(
        "INSERT INTO demo_dm.dws_order SELECT @etl_date;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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
    config.clear_model_metadata_cache()

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_baseline_ddl",
        lambda project, base_ref, repo_root=None: {
            "dws_order": "CREATE TABLE demo_dm.dws_order (order_id BIGINT) ENGINE=OLAP;\nINSERT INTO demo_dm.dws_order VALUES (1);"
        },
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.derive_project_ddl_changes",
        lambda project, base_ref, repo_root=None: [
            {
                "change_type": "ALTER",
                "table_name": "demo_dm.dws_order",
                "sql": "ALTER TABLE demo_dm.dws_order ADD COLUMN amount DECIMAL(10,2);",
            }
        ],
    )

    change_analysis = {
        "affected_scope": {
            "direct_tables": ["dwd_order"],
            "downstream_tables": ["ads_order"],
            "assessment_tables": ["dws_order"],
            "assessment_tasks": ["dws_order"],
            "anchor_tables": ["dws_order"],
        }
    }

    plan = build_verification_plan(
        "demo",
        change_analysis,
        base_ref="abc123",
        repo_root=tmp_path,
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "ods_order.id"},
                    "target": {"type": "column", "id": "dws_order.id"},
                }
            ]
        },
    )

    assert plan["project"] == "demo"
    assert plan["project_db"] == "demo_dm"
    assert plan["qa_db"] == "demo_dm_qa"
    assert plan["affected_scope"] == {
        "direct_tables": ["dwd_order"],
        "downstream_tables": ["ads_order"],
        "assessment_tables": ["dws_order"],
        "assessment_tasks": ["dws_order"],
        "anchor_tables": ["dws_order"],
        "global_dimensions": [],
    }
    assert plan["anchors"] == ["dws_order"]
    assert plan["downstream_tables"] == ["ads_order"]
    assert plan["modified_jobs"] == ["dws_order"]
    assert plan["baseline_ddl"] == {
        "dws_order": "CREATE TABLE demo_dm.dws_order (order_id BIGINT) ENGINE=OLAP;"
    }
    assert plan["ddl_changes"] == [
        {
            "change_type": "ALTER",
            "table_name": "demo_dm.dws_order",
            "sql": "ALTER TABLE demo_dm.dws_order ADD COLUMN amount DECIMAL(10,2);",
        }
    ]
    assert plan["jobs_to_run"] == [
        {
            "job": "dws_order",
            "file": "demo/mid/tasks/dws_order.sql",
            "layer": "DWS",
            "target": "dws_order",
            "needs_etl_date": True,
        }
    ]
    assert "checks" not in plan
    assert plan["verification"]["checks"] == [
        {"table": "dws_order", "method": "count"},
        {"table": "dws_order", "method": "row_compare"},
    ]

    config.clear_model_metadata_cache()


def test_build_verification_plan_requires_lineage_when_jobs_exist(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "tasks" / "dws_order.sql").write_text(
        "INSERT INTO demo_dm.dws_order SELECT 1;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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

    for lineage_data in (None, {"edges": []}):
        try:
            build_verification_plan(
                "demo",
                {
                    "affected_scope": {
                        "assessment_tables": ["dws_order"],
                        "assessment_tasks": ["dws_order"],
                        "anchor_tables": ["dws_order"],
                    }
                },
                lineage_data=lineage_data,
            )
        except ValueError as exc:
            assert "lineage" in str(exc)
        else:
            raise AssertionError("expected missing lineage to fail")


def test_build_verification_plan_preserves_empty_modified_jobs(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "tasks" / "dws_order.sql").write_text(
        "INSERT INTO demo_dm.dws_order SELECT 1;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {"task_jobs": []},
            "affected_scope": {
                "assessment_tables": ["dws_order"],
                "assessment_tasks": ["dws_order"],
                "anchor_tables": ["dws_order"],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "ods_order.id"},
                    "target": {"type": "column", "id": "dws_order.id"},
                }
            ]
        },
    )

    assert plan["modified_jobs"] == []
    assert [job["job"] for job in plan["jobs_to_run"]] == ["dws_order"]


def test_build_verification_plan_self_anchors_sql_only_task_without_downstream(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "ddl" / "dws_terminal.sql").write_text(
        "CREATE TABLE demo_dm.dws_terminal (id BIGINT) ENGINE=OLAP;",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dws_terminal.yaml").write_text(
        "version: 2\nname: dws_terminal\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_terminal.sql").write_text(
        "INSERT INTO demo_dm.dws_terminal SELECT id FROM demo_dm.ods_order;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {"task_jobs": ["dws_terminal"]},
            "affected_scope": {
                "direct_tables": ["dws_terminal"],
                "assessment_tables": ["dws_terminal"],
                "assessment_tasks": ["dws_terminal"],
                "anchor_tables": [],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "ods_order.id"},
                    "target": {"type": "column", "id": "dws_terminal.id"},
                }
            ]
        },
    )

    assert plan["anchors"] == ["dws_terminal"]
    assert plan["verification"]["data_anchor_status"] == "self_anchor_warning"
    assert plan["verification"]["self_anchor_tables"] == ["dws_terminal"]
    assert "fallback self-anchor" in plan["verification"]["data_anchor_reason"]
    assert plan["verification"]["warnings"] == [
        {
            "type": "fallback_self_anchor",
            "tables": ["dws_terminal"],
            "message": (
                "No downstream data anchor is available; using SQL-only "
                "changed terminal tables as fallback anchors. Passing compare "
                "does not prove SQL semantic equivalence."
            ),
        }
    ]
    assert plan["verification"]["checks"] == [
        {"table": "dws_terminal", "method": "count"},
        {"table": "dws_terminal", "method": "row_compare"},
    ]

    config.clear_model_metadata_cache()


def test_build_verification_plan_does_not_self_anchor_when_downstream_anchor_exists(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    for table_name, layer in [
        ("dws_terminal", "DWS"),
        ("ads_final", "ADS"),
    ]:
        (project_dir / "mid" / "ddl" / f"{table_name}.sql").write_text(
            f"CREATE TABLE demo_dm.{table_name} (id BIGINT) ENGINE=OLAP;",
            encoding="utf-8",
        )
        (project_dir / "mid" / "models" / f"{table_name}.yaml").write_text(
            f"version: 2\nname: {table_name}\nlayer: {layer}\n",
            encoding="utf-8",
        )
        (project_dir / "mid" / "tasks" / f"{table_name}.sql").write_text(
            f"INSERT INTO demo_dm.{table_name} SELECT id FROM demo_dm.ods_order;",
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {"task_jobs": ["dws_terminal"]},
            "affected_scope": {
                "direct_tables": ["dws_terminal"],
                "downstream_tables": ["ads_final"],
                "assessment_tables": ["ads_final", "dws_terminal"],
                "assessment_tasks": ["ads_final", "dws_terminal"],
                "anchor_tables": ["ads_final"],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "dws_terminal.id"},
                    "target": {"type": "column", "id": "ads_final.id"},
                }
            ]
        },
    )

    assert plan["anchors"] == ["ads_final"]
    assert plan["verification"]["data_anchor_status"] == "ready"
    assert "self_anchor_tables" not in plan["verification"]
    assert plan["verification"]["checks"] == [
        {"table": "ads_final", "method": "count"},
        {"table": "ads_final", "method": "row_compare"},
    ]

    config.clear_model_metadata_cache()


def test_build_verification_plan_blocks_ads_ddl_changes(tmp_path, monkeypatch):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "ddl" / "ads_final.sql").write_text(
        (
            "CREATE TABLE demo_dm.ads_final "
            "(id BIGINT, amount DECIMAL(10,2)) ENGINE=OLAP;"
        ),
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "ads_final.yaml").write_text(
        "version: 2\nname: ads_final\nlayer: ADS\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "ads_final.sql").write_text(
        "INSERT INTO demo_dm.ads_final SELECT id, amount FROM demo_dm.dws_order;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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
    config.clear_model_metadata_cache()
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_baseline_ddl",
        lambda project, base_ref, repo_root=None: {
            "ads_final": (
                "CREATE TABLE demo_dm.ads_final (id BIGINT) ENGINE=OLAP;"
            )
        },
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.derive_project_ddl_changes",
        lambda project, base_ref, repo_root=None: [
            {
                "change_type": "ALTER",
                "table_name": "demo_dm.ads_final",
                "sql": (
                    "ALTER TABLE demo_dm.ads_final "
                    "ADD COLUMN amount DECIMAL(10,2);"
                ),
            }
        ],
    )

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "ddl_tables": ["ads_final"],
                "task_jobs": ["ads_final"],
            },
            "affected_scope": {
                "direct_tables": ["ads_final"],
                "assessment_tables": ["ads_final"],
                "assessment_tasks": ["ads_final"],
                "anchor_tables": [],
            },
        },
        base_ref="abc123",
        repo_root=tmp_path,
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "dws_order.id"},
                    "target": {"type": "column", "id": "ads_final.id"},
                }
            ]
        },
    )

    assert plan["anchors"] == []
    assert plan["verification"]["schema_anchor_status"] == "blocked"
    assert plan["verification"]["blocked_schema_tables"] == ["ads_final"]
    assert (
        "ADS table definitions must remain unchanged"
        in plan["verification"]["schema_anchor_reason"]
    )

    config.clear_model_metadata_cache()


def test_build_verification_plan_marks_no_data_anchor_for_terminal_ddl_change(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "ddl" / "dws_terminal.sql").write_text(
        "CREATE TABLE demo_dm.dws_terminal (id BIGINT) ENGINE=OLAP;",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dws_terminal.yaml").write_text(
        "version: 2\nname: dws_terminal\nlayer: DWS\n",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_terminal.sql").write_text(
        "INSERT INTO demo_dm.dws_terminal SELECT id FROM demo_dm.ods_order;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {"ddl_tables": ["dws_terminal"]},
            "affected_scope": {
                "direct_tables": ["dws_terminal"],
                "assessment_tables": ["dws_terminal"],
                "assessment_tasks": ["dws_terminal"],
                "anchor_tables": [],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "ods_order.id"},
                    "target": {"type": "column", "id": "dws_terminal.id"},
                }
            ]
        },
    )

    assert plan["anchors"] == []
    assert plan["verification"]["checks"] == []
    assert plan["verification"]["data_anchor_status"] == "none"
    assert (
        "no invariant downstream" in plan["verification"]["data_anchor_reason"]
    )

    config.clear_model_metadata_cache()


def test_build_verification_plan_rejects_cyclic_job_lineage(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    for table_name in ["dwd_order", "dws_order"]:
        (project_dir / "mid" / "tasks" / f"{table_name}.sql").write_text(
            f"INSERT INTO demo_dm.{table_name} SELECT 1;",
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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

    try:
        build_verification_plan(
            "demo",
            {
                "affected_scope": {
                    "assessment_tables": ["dwd_order", "dws_order"],
                    "assessment_tasks": ["dwd_order", "dws_order"],
                    "anchor_tables": ["dws_order"],
                }
            },
            lineage_data={
                "edges": [
                    {
                        "source": {"type": "column", "id": "dwd_order.id"},
                        "target": {"type": "column", "id": "dws_order.id"},
                    },
                    {
                        "source": {"type": "column", "id": "dws_order.id"},
                        "target": {"type": "column", "id": "dwd_order.id"},
                    },
                ]
            },
        )
    except ValueError as exc:
        assert "cycle" in str(exc).lower()
    else:
        raise AssertionError("expected cyclic lineage to fail")


def test_build_verification_plan_applies_manual_partition_to_checks(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "mid" / "tasks" / "dws_order.sql").write_text(
        "INSERT INTO demo_dm.dws_order SELECT @etl_date;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_baseline_ddl",
        lambda project, base_ref, repo_root=None: {
            "dws_order": """CREATE TABLE demo_dm.dws_order (
  stat_date DATE NOT NULL
) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p202501 VALUES LESS THAN ("2025-02-01")
)
DISTRIBUTED BY HASH(stat_date) BUCKETS 1
PROPERTIES ("replication_num" = "1");"""
        },
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.derive_project_ddl_changes",
        lambda project, base_ref, repo_root=None: [],
    )

    plan = build_verification_plan(
        "demo",
        {
            "affected_scope": {
                "assessment_tables": ["dws_order"],
                "assessment_tasks": ["dws_order"],
                "anchor_tables": ["dws_order"],
            }
        },
        base_ref="abc123",
        repo_root=tmp_path,
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "ods_order.id"},
                    "target": {"type": "column", "id": "dws_order.id"},
                }
            ]
        },
        partition="2025-01-15",
    )

    assert plan["partition_info"] == {
        "partition": "2025-01-15",
        "etl_date": "2025-01-15",
        "per_table": {
            "dws_order": {
                "partition_col": "stat_date",
                "value": "2025-01-15",
            }
        },
    }
    assert "checks" not in plan
    assert plan["verification"]["checks"] == [
        {
            "table": "dws_order",
            "method": "count",
            "partition_col": "stat_date",
            "partition_value": "2025-01-15",
        },
        {
            "table": "dws_order",
            "method": "row_compare",
            "partition_col": "stat_date",
            "partition_value": "2025-01-15",
        },
    ]


def test_build_verification_plan_orders_jobs_topologically(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    for table_name, layer in [
        ("dwd_order", "DWD"),
        ("dws_order", "DWS"),
        ("ads_order", "ADS"),
    ]:
        (project_dir / "mid" / "ddl" / f"{table_name}.sql").write_text(
            f"CREATE TABLE demo_dm.{table_name} (id BIGINT) ENGINE=OLAP;",
            encoding="utf-8",
        )
        (project_dir / "mid" / "models" / f"{table_name}.yaml").write_text(
            f"version: 2\nname: {table_name}\nlayer: {layer}\n",
            encoding="utf-8",
        )
        (project_dir / "mid" / "tasks" / f"{table_name}.sql").write_text(
            f"INSERT INTO demo_dm.{table_name} SELECT 1;",
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
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
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "affected_scope": {
                "assessment_tables": [
                    "ads_order",
                    "dws_order",
                    "dwd_order",
                ],
                "assessment_tasks": [
                    "ads_order",
                    "dws_order",
                    "dwd_order",
                ],
                "anchor_tables": ["ads_order"],
            }
        },
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "dwd_order.id"},
                    "target": {"type": "column", "id": "dws_order.id"},
                },
                {
                    "source": {"type": "column", "id": "dws_order.id"},
                    "target": {"type": "column", "id": "ads_order.id"},
                },
            ]
        },
    )

    assert [job["job"] for job in plan["jobs_to_run"]] == [
        "dwd_order",
        "dws_order",
        "ads_order",
    ]

    config.clear_model_metadata_cache()


def test_strip_insert_data_removes_data_after_first_insert():
    ddl = """DROP TABLE IF EXISTS demo_dm.ods_order;
CREATE TABLE demo_dm.ods_order (id BIGINT) ENGINE=OLAP;

INSERT INTO demo_dm.ods_order VALUES (1);
SELECT 1;
"""

    result = strip_insert_data(ddl)

    assert "CREATE TABLE" in result
    assert "INSERT" not in result
    assert "SELECT" not in result


def test_load_baseline_ddl_reads_git_ref_and_strips_insert(monkeypatch):
    calls = []

    def fake_load_git_ddl_texts(repo, ddl_dir_rel, ref):
        calls.append((repo, ddl_dir_rel, ref))
        return {
            "dwd_order": (
                "CREATE TABLE demo_dm.dwd_order (id BIGINT) ENGINE=OLAP;\n"
                "INSERT INTO demo_dm.dwd_order VALUES (1);"
            )
        }

    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {"dir": "demo", "db": "demo_dm", "qa_db": "demo_dm_qa"},
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_git_ddl_texts",
        fake_load_git_ddl_texts,
    )

    result = load_baseline_ddl("demo", "abc123", repo_root="/repo")

    assert result == {
        "dwd_order": "CREATE TABLE demo_dm.dwd_order (id BIGINT) ENGINE=OLAP;"
    }
    assert calls == [
        (Path("/repo"), "demo/mid/ddl", "abc123"),
        (Path("/repo"), "demo/ads/ddl", "abc123"),
    ]


def test_load_baseline_ddl_merges_mid_and_ads_git_dirs(monkeypatch):
    def fake_load_git_ddl_texts(_repo, ddl_dir_rel, _ref):
        if ddl_dir_rel.endswith("/mid/ddl"):
            return {
                "dwd_order": (
                    "CREATE TABLE demo_dm.dwd_order (id BIGINT) ENGINE=OLAP;"
                )
            }
        if ddl_dir_rel.endswith("/ads/ddl"):
            return {
                "ads_order": (
                    "CREATE TABLE demo_dm.ads_order (id BIGINT) ENGINE=OLAP;"
                )
            }
        return {}

    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {"dir": "demo", "db": "demo_dm", "qa_db": "demo_dm_qa"},
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_git_ddl_texts",
        fake_load_git_ddl_texts,
    )

    result = load_baseline_ddl("demo", "abc123", repo_root="/repo")

    assert result == {
        "ads_order": "CREATE TABLE demo_dm.ads_order (id BIGINT) ENGINE=OLAP;",
        "dwd_order": "CREATE TABLE demo_dm.dwd_order (id BIGINT) ENGINE=OLAP;",
    }


def test_parse_partition_col_from_ddl_and_get_partition_col():
    ddl = """CREATE TABLE demo_dm.dwd_order (
        order_date DATE NOT NULL
    ) ENGINE=OLAP
    PARTITION BY RANGE(order_date) (
        PARTITION p202501 VALUES LESS THAN ("2025-02-01")
    )
    DISTRIBUTED BY HASH(order_date) BUCKETS 1
    PROPERTIES ("replication_num" = "1");"""

    assert parse_partition_col_from_ddl(ddl) == "order_date"
    assert get_partition_col("dwd_order", {"dwd_order": ddl}) == "order_date"
    assert get_partition_col("missing", {"dwd_order": ddl}) == ""
