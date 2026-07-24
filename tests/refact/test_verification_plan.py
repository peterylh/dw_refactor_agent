import ast
from datetime import date
from pathlib import Path

import pytest

import dw_refactor_agent.config as config
import dw_refactor_agent.refactor.verification_plan as verification_plan_module
from dw_refactor_agent.ddl_deriver.ddl_deriver import (
    ColumnDef,
    TableDef,
    parse_create_table,
)
from dw_refactor_agent.ddl_deriver.schema_ids import SchemaIdentityError
from dw_refactor_agent.execution.planner import ExecutionPlanner
from dw_refactor_agent.execution.schedule_graph import ScheduleGraph
from dw_refactor_agent.refactor.semantic_mode import SemanticResolution
from dw_refactor_agent.refactor.shadow_manifest import (
    compile_shadow_manifest,
    manifest_summary,
)
from dw_refactor_agent.refactor.verification_plan import (
    build_verification_plan,
    derive_project_ddl_changes,
    get_partition_col,
    load_baseline_ddl,
    parse_partition_col_from_ddl,
    strip_insert_data,
)

TABLE_ID = "91ed8f6a-736d-4896-888e-f9225741b7fa"
COLUMN_ID = "6bfa89c0-1e30-4f92-a25e-b5a39ab94880"
_UNSET = object()


def _check_group(
    table,
    *,
    scope=None,
    exclude_columns=_UNSET,
    prod_table=None,
    qa_table=None,
    column_mapping=None,
):
    group = {
        "table": table,
        "scope": scope or {"mode": "full_table"},
        "methods": [{"method": "count"}, {"method": "row_compare"}],
    }
    if exclude_columns is not _UNSET:
        group["methods"][1]["exclude_columns"] = exclude_columns
    if prod_table:
        group["prod_table"] = prod_table
    if qa_table:
        group["qa_table"] = qa_table
    if column_mapping:
        group["column_mapping"] = column_mapping
    return group


def _configure_identity_project(tmp_path, monkeypatch, ddl):
    project_dir = tmp_path / "demo"
    ddl_dir = project_dir / "mid" / "ddl"
    ddl_dir.mkdir(parents=True)
    (ddl_dir / "dwd_order.sql").write_text(ddl, encoding="utf-8")
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


def test_derive_project_ddl_changes_rejects_missing_worktree_ids(
    tmp_path, monkeypatch
):
    _configure_identity_project(
        tmp_path,
        monkeypatch,
        """\
CREATE TABLE demo_dm.dwd_order (
    order_id BIGINT NOT NULL
) ENGINE=OLAP;
""",
    )

    with pytest.raises(SchemaIdentityError, match="missing_table_id"):
        derive_project_ddl_changes("demo", "base", repo_root=tmp_path)


def test_derive_project_ddl_changes_rejects_missing_baseline_ids(
    tmp_path, monkeypatch
):
    _configure_identity_project(
        tmp_path,
        monkeypatch,
        f"""\
-- table_id: {TABLE_ID}
CREATE TABLE demo_dm.dwd_order (
    -- column_id: {COLUMN_ID}
    order_id BIGINT NOT NULL
) ENGINE=OLAP;
""",
    )
    old_table = TableDef(
        full_name="demo_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("order_id", "BIGINT", nullable=False)],
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_git_tables",
        lambda repo, ddl_rel, base_ref: (
            {"dwd_order": old_table} if "/mid/" in ddl_rel else {}
        ),
    )

    with pytest.raises(SchemaIdentityError, match="missing_table_id"):
        derive_project_ddl_changes("demo", "base", repo_root=tmp_path)


def test_derive_project_ddl_changes_uses_ids_for_column_rename(
    tmp_path, monkeypatch
):
    _configure_identity_project(
        tmp_path,
        monkeypatch,
        f"""\
-- table_id: {TABLE_ID}
CREATE TABLE demo_dm.dwd_order (
    -- column_id: {COLUMN_ID}
    order_number BIGINT NOT NULL
) ENGINE=OLAP;
""",
    )
    old_table = TableDef(
        full_name="demo_dm.dwd_order",
        short_name="dwd_order",
        table_id=TABLE_ID,
        columns=[
            ColumnDef(
                "order_id",
                "BIGINT",
                nullable=False,
                column_id=COLUMN_ID,
            )
        ],
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_git_tables",
        lambda repo, ddl_rel, base_ref: (
            {"dwd_order": old_table} if "/mid/" in ddl_rel else {}
        ),
    )

    changes = derive_project_ddl_changes("demo", "base", repo_root=tmp_path)

    assert len(changes) == 1
    assert changes[0]["change_type"] == "ALTER"
    assert changes[0]["renames"] == [
        {
            "old": "order_id",
            "new": "order_number",
            "column_id": COLUMN_ID,
            "matched_by": "column_id",
        }
    ]


def test_derive_project_ddl_changes_includes_physical_partition_rebuild(
    tmp_path, monkeypatch
):
    old_ddl = f"""\
-- table_id: {TABLE_ID}
CREATE TABLE demo_dm.dwd_order (
    -- column_id: {COLUMN_ID}
    order_id BIGINT NOT NULL
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 4;
"""
    new_ddl = old_ddl.replace(
        "DISTRIBUTED BY HASH(order_id)",
        "AUTO PARTITION BY LIST (`order_id`) ()\n"
        "DISTRIBUTED BY HASH(order_id)",
    )
    _configure_identity_project(tmp_path, monkeypatch, new_ddl)
    old_table = parse_create_table(old_ddl)
    assert old_table is not None
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.load_git_tables",
        lambda repo, ddl_rel, base_ref: (
            {"dwd_order": old_table} if "/mid/" in ddl_rel else {}
        ),
    )

    changes = derive_project_ddl_changes("demo", "base", repo_root=tmp_path)

    assert [change["change_type"] for change in changes] == ["DROP", "CREATE"]
    assert "AUTO PARTITION BY LIST" in changes[1]["sql"]


_NO_PARTITION = object()


def _build_single_anchor_plan(
    tmp_path,
    monkeypatch,
    table_name,
    model_yaml,
    *,
    task_sql="INSERT INTO demo_dm.{table_name} SELECT 1;",
    partition="2024-06-15",
    verification=None,
):
    project_dir = tmp_path / "demo"
    (project_dir / "ads" / "models").mkdir(parents=True)
    (project_dir / "ads" / "tasks").mkdir()
    (project_dir / "ads" / "models" / f"{table_name}.yaml").write_text(
        model_yaml,
        encoding="utf-8",
    )
    (project_dir / "ads" / "tasks" / f"{table_name}.sql").write_text(
        task_sql.format(table_name=table_name),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    project_config = {
        "dir": "demo",
        "db": "demo_dm",
        "qa_db": "demo_dm_qa",
        "catalog": "internal",
    }
    if verification is not None:
        project_config["verification"] = verification
    monkeypatch.setitem(config.PROJECT_CONFIG, "demo", project_config)
    config.clear_model_metadata_cache()

    kwargs = {}
    if partition is not _NO_PARTITION:
        kwargs["partition"] = partition
    return build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": [table_name],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": [table_name],
                "downstream_tables": [],
                "assessment_tables": [table_name],
                "assessment_tasks": [table_name],
                "anchor_tables": [table_name],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "ods_order.id"},
                    "target": {
                        "type": "column",
                        "id": f"{table_name}.id",
                    },
                }
            ]
        },
        **kwargs,
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
            "lineage_db": "demo_lineage",
            "catalog": "internal",
            "verification": {
                "qa_database_pool": ["demo_dm_qa", "demo_dm_qa_02"],
                "row_compare": {
                    "exclude_columns": ["etl_time"],
                    "tables": {
                        "dws_order": {
                            "exclude_columns": ["etl_time", "update_time"]
                        }
                    },
                },
            },
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
        "changed_assets": {
            "task_jobs": ["dws_order"],
            "ddl_tables": ["dws_order"],
            "model_tables": ["dws_order"],
            "config_files": ["demo/naming_config.yaml"],
        },
        "affected_scope": {
            "direct_tables": ["dws_order"],
            "downstream_tables": [],
            "assessment_tables": ["dws_order"],
            "assessment_tasks": ["dws_order"],
            "anchor_tables": ["dws_order"],
        },
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
    assert plan["qa_database_pool"] == ["demo_dm_qa", "demo_dm_qa_02"]
    assert "affected_scope" not in plan
    assert "modified_jobs" not in plan
    assert "downstream_tables" not in plan
    assert "anchors" not in plan
    assert "scope" not in plan
    assert plan["changes"] == {
        "modified_jobs": ["dws_order"],
        "ddl_tables": ["dws_order"],
        "model_tables": ["dws_order"],
        "config_files": ["demo/naming_config.yaml"],
    }
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
        }
    ]
    assert "checks" not in plan
    assert plan["verification"]["anchor_tables"] == ["dws_order"]
    assert plan["verification"]["checks"] == [
        _check_group("dws_order", exclude_columns=["etl_time", "update_time"])
    ]

    config.clear_model_metadata_cache()


def test_build_verification_plan_writes_row_compare_exclude_columns_from_config(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo",
            "db": "demo_dm",
            "qa_db": "demo_dm_qa",
            "catalog": "internal",
            "verification": {
                "row_compare": {
                    "exclude_columns": ["etl_time"],
                    "tables": {
                        "dws_order": {
                            "exclude_columns": ["etl_time", "update_time"]
                        },
                        "ads_full_audit": {"exclude_columns": []},
                    },
                }
            },
        },
    )
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": [],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": ["demo/warehouse.yaml"],
            },
            "affected_scope": {
                "direct_tables": [],
                "downstream_tables": [],
                "assessment_tables": [
                    "ads_full_audit",
                    "dws_customer",
                    "dws_order",
                ],
                "anchor_tables": [
                    "ads_full_audit",
                    "dws_customer",
                    "dws_order",
                ],
            },
        },
    )

    assert plan["verification"]["checks"] == [
        _check_group("ads_full_audit", exclude_columns=[]),
        _check_group("dws_customer", exclude_columns=["etl_time"]),
        _check_group("dws_order", exclude_columns=["etl_time", "update_time"]),
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
                    "changed_assets": {
                        "task_jobs": ["dws_order"],
                        "ddl_tables": [],
                        "model_tables": [],
                        "config_files": [],
                    },
                    "affected_scope": {
                        "direct_tables": ["dws_order"],
                        "downstream_tables": [],
                        "assessment_tables": ["dws_order"],
                        "assessment_tasks": ["dws_order"],
                        "anchor_tables": ["dws_order"],
                    },
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
            "changed_assets": {
                "task_jobs": [],
                "ddl_tables": [],
                "model_tables": ["dws_order"],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dws_order"],
                "downstream_tables": [],
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

    assert plan["changes"]["modified_jobs"] == []
    assert [job["job"] for job in plan["jobs_to_run"]] == ["dws_order"]


def test_build_verification_plan_requires_changed_assets(
    tmp_path, monkeypatch
):
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

    with pytest.raises(ValueError, match="changed_assets"):
        build_verification_plan(
            "demo",
            {
                "affected_scope": {
                    "direct_tables": [],
                    "downstream_tables": [],
                    "assessment_tables": [],
                    "assessment_tasks": [],
                    "anchor_tables": [],
                }
            },
            repo_root=tmp_path,
        )


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

    assert plan["verification"]["anchor_tables"] == ["dws_terminal"]
    assert plan["verification"]["data_anchor_status"] == "self_anchor_warning"
    assert plan["verification"]["self_anchor_tables"] == ["dws_terminal"]
    assert "fallback self-anchor" in plan["verification"]["data_anchor_reason"]
    assert plan["verification"]["warnings"] == [
        {
            "type": "full_table_compare",
            "tables": ["dws_terminal"],
            "message": (
                "No execution slice metadata is configured; full-table "
                "compare will be used."
            ),
        },
        {
            "type": "fallback_self_anchor",
            "tables": ["dws_terminal"],
            "message": (
                "No downstream data anchor is available; using SQL-only "
                "changed terminal tables as fallback anchors. Passing compare "
                "does not prove SQL semantic equivalence."
            ),
        },
    ]
    assert plan["verification"]["checks"] == [
        _check_group("dws_terminal"),
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

    assert plan["verification"]["anchor_tables"] == ["ads_final"]
    assert plan["verification"]["data_anchor_status"] == "ready"
    assert "self_anchor_tables" not in plan["verification"]
    assert plan["verification"]["checks"] == [
        _check_group("ads_final"),
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

    assert plan["verification"]["anchor_tables"] == []
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

    assert plan["verification"]["anchor_tables"] == []
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
                "changed_assets": {
                    "task_jobs": ["dwd_order"],
                    "ddl_tables": [],
                    "model_tables": [],
                    "config_files": [],
                },
                "affected_scope": {
                    "direct_tables": ["dwd_order"],
                    "downstream_tables": ["dws_order"],
                    "assessment_tables": ["dwd_order", "dws_order"],
                    "assessment_tasks": ["dwd_order", "dws_order"],
                    "anchor_tables": ["dws_order"],
                },
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
            "changed_assets": {
                "task_jobs": ["dws_order"],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dws_order"],
                "downstream_tables": [],
                "assessment_tables": ["dws_order"],
                "assessment_tasks": ["dws_order"],
                "anchor_tables": ["dws_order"],
            },
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

    assert "partition_info" not in plan
    assert "checks" not in plan
    assert plan["verification"]["checks"] == [
        _check_group("dws_order"),
    ]
    assert plan["verification"]["warnings"] == [
        {
            "type": "full_table_compare",
            "tables": ["dws_order"],
            "message": (
                "No execution slice metadata is configured; full-table "
                "compare will be used."
            ),
        }
    ]


def test_build_verification_plan_uses_execution_slice_for_compare_and_values(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "ads" / "tasks").mkdir(parents=True)
    (project_dir / "ads" / "models").mkdir()
    (project_dir / "warehouse.yaml").write_text(
        """name: demo
catalog: internal
database: demo_dm
qa_database: demo_dm_qa
execution:
  default_slice:
    param: etl_date
    column: stat_date
    period: D
""",
        encoding="utf-8",
    )
    (project_dir / "mid" / "models" / "dws_store_sales_daily.yaml").write_text(
        """version: 2
name: dws_store_sales_daily
layer: DWS
execution:
  materialized: incremental
""",
        encoding="utf-8",
    )
    (project_dir / "ads" / "models" / "ads_store_performance.yaml").write_text(
        """version: 2
name: ads_store_performance
layer: ADS
execution:
  materialized: incremental
  slice:
    param: etl_month
    column: stat_month_date
    period: M
""",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_store_sales_daily.sql").write_text(
        "INSERT INTO demo_dm.dws_store_sales_daily SELECT @etl_date;",
        encoding="utf-8",
    )
    (project_dir / "ads" / "tasks" / "ads_store_performance.sql").write_text(
        "INSERT INTO demo_dm.ads_store_performance SELECT @etl_month;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        config.core.load_warehouse_config(
            project_dir / "warehouse.yaml",
            project_root=tmp_path,
        ),
    )
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": ["dws_store_sales_daily"],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dws_store_sales_daily"],
                "downstream_tables": ["ads_store_performance"],
                "assessment_tables": [
                    "dws_store_sales_daily",
                    "ads_store_performance",
                ],
                "assessment_tasks": [
                    "dws_store_sales_daily",
                    "ads_store_performance",
                ],
                "anchor_tables": ["ads_store_performance"],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {
                        "type": "column",
                        "id": "dws_store_sales_daily.store_id",
                    },
                    "target": {
                        "type": "column",
                        "id": "ads_store_performance.store_id",
                    },
                }
            ]
        },
        partition="2024-06-15",
    )

    assert plan["verification"]["checks"] == [
        _check_group(
            "ads_store_performance",
            scope={
                "mode": "time_slice",
                "column": "stat_month_date",
                "period": "M",
                "value": "2024-06-01",
            },
        )
    ]
    jobs = {job["job"]: job for job in plan["jobs_to_run"]}
    assert jobs["dws_store_sales_daily"]["execution_values"][0] == "2024-06-01"
    assert (
        jobs["dws_store_sales_daily"]["execution_values"][-1] == "2024-06-30"
    )
    assert len(jobs["dws_store_sales_daily"]["execution_values"]) == 30
    assert jobs["ads_store_performance"]["execution_values"] == ["2024-06-01"]
    assert "refresh_parameter" not in jobs["dws_store_sales_daily"]
    assert "refresh_time_period" not in jobs["dws_store_sales_daily"]

    config.clear_model_metadata_cache()


@pytest.mark.parametrize("use_base_ref", [False, True])
def test_build_verification_plan_excludes_unchanged_upstream_from_jobs(
    tmp_path, monkeypatch, use_base_ref
):
    project_dir = tmp_path / "demo"
    for asset_dir in ("mid", "ads"):
        (project_dir / asset_dir / "tasks").mkdir(parents=True)
        (project_dir / asset_dir / "models").mkdir()
        (project_dir / asset_dir / "ddl").mkdir()
    (project_dir / "warehouse.yaml").write_text(
        """name: demo
catalog: internal
database: demo_dm
qa_database: demo_dm_qa
execution:
  default_slice:
    param: etl_date
    column: stat_date
    period: D
""",
        encoding="utf-8",
    )

    def write_job(asset_dir, name, layer, period="D"):
        (project_dir / asset_dir / "models" / f"{name}.yaml").write_text(
            f"""version: 2
name: {name}
layer: {layer}
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: stat_date
    period: {period}
""",
            encoding="utf-8",
        )
        (project_dir / asset_dir / "tasks" / f"{name}.sql").write_text(
            f"INSERT INTO demo_dm.{name} SELECT @etl_date;",
            encoding="utf-8",
        )
        (project_dir / asset_dir / "ddl" / f"{name}.sql").write_text(
            f"CREATE TABLE demo_dm.{name} (id BIGINT) ENGINE=OLAP;",
            encoding="utf-8",
        )

    write_job("mid", "dwd_order_detail", "DWD")
    write_job("mid", "dws_category_sales_daily", "DWS")
    write_job("ads", "ads_store_performance", "ADS", "M")
    (
        project_dir / "mid" / "tasks" / "dws_category_sales_daily.sql"
    ).write_text(
        "INSERT INTO demo_dm.dws_category_sales_daily "
        "SELECT * FROM demo_dm.dwd_order_detail "
        "WHERE stat_date = @etl_date;",
        encoding="utf-8",
    )
    (project_dir / "ads" / "tasks" / "ads_store_performance.sql").write_text(
        "INSERT INTO demo_dm.ads_store_performance "
        "SELECT * FROM demo_dm.dws_category_sales_daily "
        "WHERE stat_date = @etl_date;",
        encoding="utf-8",
    )

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        config.core.load_warehouse_config(
            project_dir / "warehouse.yaml",
            project_root=tmp_path,
        ),
    )
    config.clear_model_metadata_cache()
    if use_base_ref:
        monkeypatch.setattr(
            "dw_refactor_agent.refactor.verification_plan.load_baseline_ddl",
            lambda project, base_ref, repo_root=None: {
                table: (
                    f"CREATE TABLE demo_dm.{table} (id BIGINT) ENGINE=OLAP;"
                )
                for table in (
                    "dwd_order_detail",
                    "dws_category_sales_daily",
                    "ads_store_performance",
                )
            },
        )
        monkeypatch.setattr(
            "dw_refactor_agent.refactor.verification_plan.derive_project_ddl_changes",
            lambda project, base_ref, repo_root=None: [],
        )

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": ["dws_category_sales_daily"],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dws_category_sales_daily"],
                "downstream_tables": ["ads_store_performance"],
                "assessment_tables": [
                    "dwd_order_detail",
                    "dws_category_sales_daily",
                    "ads_store_performance",
                ],
                "assessment_tasks": [
                    "dwd_order_detail",
                    "dws_category_sales_daily",
                    "ads_store_performance",
                ],
                "anchor_tables": ["ads_store_performance"],
            },
        },
        base_ref="abc123" if use_base_ref else None,
        repo_root=tmp_path,
        lineage_data={
            "edges": [
                {
                    "source": {
                        "type": "column",
                        "id": "dwd_order_detail.order_id",
                    },
                    "target": {
                        "type": "column",
                        "id": "dws_category_sales_daily.order_id",
                    },
                },
                {
                    "source": {
                        "type": "column",
                        "id": "dws_category_sales_daily.store_id",
                    },
                    "target": {
                        "type": "column",
                        "id": "ads_store_performance.store_id",
                    },
                },
            ]
        },
        partition="2024-06-15",
    )

    jobs = {job["job"]: job for job in plan["jobs_to_run"]}
    assert sorted(jobs) == [
        "ads_store_performance",
        "dws_category_sales_daily",
    ]
    assert len(jobs["dws_category_sales_daily"]["execution_values"]) == 30
    assert jobs["ads_store_performance"]["execution_values"] == ["2024-06-01"]
    assert sorted(plan["baseline_ddl"]) == [
        "ads_store_performance",
        "dws_category_sales_daily",
    ]
    summary = manifest_summary(
        compile_shadow_manifest(
            plan,
            tmp_path,
            ExecutionPlanner("demo", project_root=tmp_path),
        )
    )
    assert summary["jobs"]["dws_category_sales_daily"]["routes"]["data_read"][
        "dwd_order_detail"
    ] == {
        "database": "demo_dm",
        "table": "dwd_order_detail",
    }
    assert "dwd_order_detail" not in summary["writers_by_relation"]
    assert summary["blockers"] == []

    config.clear_model_metadata_cache()


def test_build_verification_plan_propagates_anchor_windows_by_lineage_path(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    for asset_dir in ("mid", "ads"):
        (project_dir / asset_dir / "tasks").mkdir(parents=True)
        (project_dir / asset_dir / "models").mkdir()
    (project_dir / "warehouse.yaml").write_text(
        """name: demo
catalog: internal
database: demo_dm
qa_database: demo_dm_qa
execution:
  default_slice:
    param: etl_date
    column: stat_date
    period: D
""",
        encoding="utf-8",
    )

    def write_job(asset_dir, name, layer, period="D"):
        (project_dir / asset_dir / "models" / f"{name}.yaml").write_text(
            f"""version: 2
name: {name}
layer: {layer}
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: stat_date
    period: {period}
""",
            encoding="utf-8",
        )
        (project_dir / asset_dir / "tasks" / f"{name}.sql").write_text(
            f"INSERT INTO demo_dm.{name} SELECT @etl_date;",
            encoding="utf-8",
        )

    write_job("mid", "dwd_order_detail", "DWD", "D")
    write_job("mid", "dws_category_sales_monthly", "DWS", "M")
    write_job("ads", "ads_category_daily_report", "ADS", "D")
    write_job("mid", "dwd_inventory", "DWD", "D")
    write_job("ads", "ads_inventory_alert", "ADS", "D")
    write_job("mid", "dwd_customer", "DWD", "D")
    write_job("ads", "ads_store_performance", "ADS", "M")

    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        config.core.load_warehouse_config(
            project_dir / "warehouse.yaml",
            project_root=tmp_path,
        ),
    )
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": [
                    "dwd_order_detail",
                    "dwd_inventory",
                    "dwd_customer",
                ],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": [
                    "dwd_order_detail",
                    "dwd_inventory",
                    "dwd_customer",
                ],
                "downstream_tables": [
                    "dws_category_sales_monthly",
                    "ads_category_daily_report",
                    "ads_inventory_alert",
                    "ads_store_performance",
                ],
                "assessment_tables": [
                    "dwd_order_detail",
                    "dws_category_sales_monthly",
                    "ads_category_daily_report",
                    "dwd_inventory",
                    "ads_inventory_alert",
                    "dwd_customer",
                    "ads_store_performance",
                ],
                "assessment_tasks": [
                    "dwd_order_detail",
                    "dws_category_sales_monthly",
                    "ads_category_daily_report",
                    "dwd_inventory",
                    "ads_inventory_alert",
                    "dwd_customer",
                    "ads_store_performance",
                ],
                "anchor_tables": [
                    "ads_category_daily_report",
                    "ads_inventory_alert",
                    "ads_store_performance",
                ],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {"type": "column", "id": "dwd_order_detail.id"},
                    "target": {
                        "type": "column",
                        "id": "dws_category_sales_monthly.id",
                    },
                },
                {
                    "source": {
                        "type": "column",
                        "id": "dws_category_sales_monthly.id",
                    },
                    "target": {
                        "type": "column",
                        "id": "ads_category_daily_report.id",
                    },
                },
                {
                    "source": {"type": "column", "id": "dwd_inventory.id"},
                    "target": {
                        "type": "column",
                        "id": "ads_inventory_alert.id",
                    },
                },
                {
                    "source": {"type": "column", "id": "dwd_customer.id"},
                    "target": {
                        "type": "column",
                        "id": "ads_store_performance.id",
                    },
                },
            ]
        },
        partition="2024-06-15",
    )

    jobs = {job["job"]: job for job in plan["jobs_to_run"]}
    assert jobs["ads_category_daily_report"]["execution_values"] == [
        "2024-06-15"
    ]
    assert jobs["dws_category_sales_monthly"]["execution_values"] == [
        "2024-06-01"
    ]
    assert jobs["dwd_order_detail"]["execution_values"][0] == "2024-06-01"
    assert jobs["dwd_order_detail"]["execution_values"][-1] == "2024-06-30"
    assert len(jobs["dwd_order_detail"]["execution_values"]) == 30
    assert jobs["ads_inventory_alert"]["execution_values"] == ["2024-06-15"]
    assert jobs["dwd_inventory"]["execution_values"] == ["2024-06-15"]
    assert jobs["ads_store_performance"]["execution_values"] == ["2024-06-01"]
    assert jobs["dwd_customer"]["execution_values"][0] == "2024-06-01"
    assert jobs["dwd_customer"]["execution_values"][-1] == "2024-06-30"
    assert len(jobs["dwd_customer"]["execution_values"]) == 30

    config.clear_model_metadata_cache()


def test_build_verification_plan_supports_hour_execution_slice(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "ads" / "models").mkdir(parents=True)
    (project_dir / "ads" / "tasks").mkdir()
    (project_dir / "warehouse.yaml").write_text(
        """name: demo
catalog: internal
database: demo_dm
qa_database: demo_dm_qa
execution:
  default_slice:
    param: etl_hour
    column: stat_hour
    period: H
""",
        encoding="utf-8",
    )
    (project_dir / "ads" / "models" / "ads_hourly.yaml").write_text(
        """version: 2
name: ads_hourly
layer: ADS
execution:
  materialized: incremental
""",
        encoding="utf-8",
    )
    (project_dir / "ads" / "tasks" / "ads_hourly.sql").write_text(
        "INSERT INTO demo_dm.ads_hourly SELECT @etl_hour;",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        config.core.load_warehouse_config(
            project_dir / "warehouse.yaml",
            project_root=tmp_path,
        ),
    )
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": ["ads_hourly"],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["ads_hourly"],
                "downstream_tables": [],
                "assessment_tables": ["ads_hourly"],
                "assessment_tasks": ["ads_hourly"],
                "anchor_tables": ["ads_hourly"],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {
                        "type": "column",
                        "id": "ods_event.event_time",
                    },
                    "target": {
                        "type": "column",
                        "id": "ads_hourly.stat_hour",
                    },
                }
            ]
        },
        partition="2024-06-01 03:20:00",
    )

    assert plan["verification"]["checks"] == [
        _check_group(
            "ads_hourly",
            scope={
                "mode": "time_slice",
                "column": "stat_hour",
                "period": "H",
                "value": "2024-06-01 03:00:00",
            },
        )
    ]
    jobs = {job["job"]: job for job in plan["jobs_to_run"]}
    assert jobs["ads_hourly"]["execution_values"] == ["2024-06-01 03:00:00"]

    config.clear_model_metadata_cache()


def test_build_verification_plan_ignores_grain_for_compare_slice(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    (project_dir / "ads" / "ddl").mkdir(parents=True)
    (project_dir / "ads" / "models").mkdir()
    (project_dir / "ads" / "tasks").mkdir()
    (project_dir / "mid" / "models" / "dws_store_sales_daily.yaml").write_text(
        """version: 2
name: dws_store_sales_daily
layer: DWS
grain:
  time_column: stat_date
  time_period: D
""",
        encoding="utf-8",
    )
    (project_dir / "ads" / "models" / "ads_store_performance.yaml").write_text(
        """version: 2
name: ads_store_performance
layer: ADS
grain:
  time_column: stat_month_date
  time_period: M
""",
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks" / "dws_store_sales_daily.sql").write_text(
        "INSERT INTO demo_dm.dws_store_sales_daily SELECT @etl_date;",
        encoding="utf-8",
    )
    (project_dir / "ads" / "tasks" / "ads_store_performance.sql").write_text(
        "INSERT INTO demo_dm.ads_store_performance SELECT @etl_date;",
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
            "verification": {
                "week_start": "MON",
            },
        },
    )
    config.clear_model_metadata_cache()

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": ["dws_store_sales_daily"],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dws_store_sales_daily"],
                "downstream_tables": ["ads_store_performance"],
                "assessment_tables": [
                    "dws_store_sales_daily",
                    "ads_store_performance",
                ],
                "assessment_tasks": [
                    "dws_store_sales_daily",
                    "ads_store_performance",
                ],
                "anchor_tables": ["ads_store_performance"],
            },
        },
        lineage_data={
            "edges": [
                {
                    "source": {
                        "type": "column",
                        "id": "dws_store_sales_daily.store_id",
                    },
                    "target": {
                        "type": "column",
                        "id": "ads_store_performance.store_id",
                    },
                }
            ]
        },
        partition="2024-06-15",
    )

    assert "partition_info" not in plan
    assert plan["verification"]["checks"] == [
        _check_group("ads_store_performance"),
    ]
    assert plan["verification"]["warnings"] == [
        {
            "type": "full_table_compare",
            "tables": ["ads_store_performance"],
            "message": (
                "No execution slice metadata is configured; full-table "
                "compare will be used."
            ),
        }
    ]
    jobs = {job["job"]: job for job in plan["jobs_to_run"]}
    assert "refresh_parameter" not in jobs["dws_store_sales_daily"]
    assert "refresh_time_period" not in jobs["dws_store_sales_daily"]
    assert "execution_values" not in jobs["dws_store_sales_daily"]
    assert "execution_values" not in jobs["ads_store_performance"]
    assert "needs_etl_date" not in jobs["dws_store_sales_daily"]

    config.clear_model_metadata_cache()


@pytest.mark.parametrize(
    "model_yaml",
    [
        "version: 2\nname: ads_dashboard\nlayer: ADS\n",
        """version: 2
name: ads_dashboard
layer: ADS
grain:
  entities:
  - STORE
""",
    ],
    ids=("without-grain", "entity-only-grain"),
)
def test_build_verification_plan_uses_full_table_compare_without_time_grain(
    tmp_path, monkeypatch, model_yaml
):
    plan = _build_single_anchor_plan(
        tmp_path,
        monkeypatch,
        "ads_dashboard",
        model_yaml,
    )

    assert plan["verification"]["data_anchor_status"] == "ready"
    assert plan["verification"]["warnings"] == [
        {
            "type": "full_table_compare",
            "tables": ["ads_dashboard"],
            "message": (
                "No execution slice metadata is configured; full-table "
                "compare will be used."
            ),
        }
    ]
    assert plan["verification"]["checks"] == [
        _check_group("ads_dashboard"),
    ]

    config.clear_model_metadata_cache()


def test_quarantined_model_keeps_operational_refactor_plan(
    tmp_path,
    monkeypatch,
):
    plan = _build_single_anchor_plan(
        tmp_path,
        monkeypatch,
        "ads_dashboard",
        """version: 3
name: ads_dashboard
operational_layer: ADS
execution:
  materialized: incremental
  full_refresh_strategy: replay_slices
  slice:
    param: etl_date
    column: stat_date
    period: D
governance:
  status: quarantined
  schema_version: 1
  withheld_sections: [classification, business_semantics, entities, grain, metrics]
  reasons:
    classification: [structure_bundle_incomplete]
    business_semantics: [business_process_missing]
    entities: [structure_bundle_incomplete]
    grain: [structure_bundle_incomplete]
    metrics: [dependent_structure_unavailable]
""",
        task_sql="INSERT INTO demo_dm.{table_name} SELECT @etl_date;",
    )

    assert plan["jobs_to_run"][0]["layer"] == "ADS"
    assert plan["jobs_to_run"][0]["execution_values"] == ["2024-06-15"]
    assert plan["verification"]["data_anchor_status"] == "ready"

    config.clear_model_metadata_cache()


def test_verification_plan_blocks_task_bound_to_taskless_model(
    tmp_path,
    monkeypatch,
):
    plan = _build_single_anchor_plan(
        tmp_path,
        monkeypatch,
        "ads_external",
        """version: 2
name: ads_external
layer: ADS
execution:
  mode: taskless
""",
    )

    assert plan["verification"]["data_anchor_status"] == "blocked"
    assert plan["verification"]["checks"] == []
    assert plan["verification"]["metadata_errors"] == [
        {
            "table": "ads_external",
            "field": "execution.mode",
            "message": (
                "[ads_external] task SQL cannot bind to "
                "execution.mode=taskless"
            ),
        }
    ]

    config.clear_model_metadata_cache()


def test_build_verification_plan_allows_ddl_only_table_without_lineage(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "models").mkdir(parents=True)
    (project_dir / "mid" / "models" / "dws_order.yaml").write_text(
        "version: 2\nname: dws_order\nlayer: DWS\n",
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
            "dws_order": (
                "CREATE TABLE demo_dm.dws_order (order_id BIGINT) ENGINE=OLAP;"
            )
        },
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.verification_plan.derive_project_ddl_changes",
        lambda project, base_ref, repo_root=None: [
            {
                "change_type": "ALTER",
                "table_name": "demo_dm.dws_order",
                "sql": (
                    "ALTER TABLE demo_dm.dws_order "
                    "ADD COLUMN amount DECIMAL(10,2);"
                ),
            }
        ],
    )

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": [],
                "ddl_tables": ["dws_order"],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dws_order"],
                "downstream_tables": [],
                "assessment_tables": ["dws_order"],
                "assessment_tasks": [],
                "anchor_tables": [],
            },
        },
        base_ref="abc123",
        repo_root=tmp_path,
        lineage_data={},
    )

    assert plan["jobs_to_run"] == []
    assert sorted(plan["baseline_ddl"]) == ["dws_order"]
    assert plan["ddl_changes"][0]["table_name"] == "demo_dm.dws_order"

    config.clear_model_metadata_cache()


def test_build_verification_plan_requires_partition_for_incremental_jobs(
    tmp_path, monkeypatch
):
    with pytest.raises(ValueError) as exc_info:
        _build_single_anchor_plan(
            tmp_path,
            monkeypatch,
            "ads_dashboard",
            """version: 2
name: ads_dashboard
layer: ADS
execution:
  slice:
    param: etl_date
    column: stat_date
    period: D
""",
            task_sql="INSERT INTO demo_dm.{table_name} SELECT @etl_date;",
            partition=_NO_PARTITION,
            verification={"week_start": "MON"},
        )

    assert "--partition" in str(exc_info.value)
    assert "ads_dashboard" in str(exc_info.value)

    config.clear_model_metadata_cache()


@pytest.mark.parametrize(
    ("table_name", "model_yaml", "partition", "expected_error"),
    [
        (
            "ads_order",
            """version: 2
name: ads_order
layer: ADS
execution:
  slice:
    param: etl_date
    column: stat_date
""",
            "2024-06-15",
            {
                "table": "ads_order",
                "field": "execution.slice",
                "message": (
                    "[ads_order] execution.slice requires param, column, "
                    "and period"
                ),
            },
        ),
        (
            "ads_weekly",
            """version: 2
name: ads_weekly
layer: ADS
execution:
  slice:
    param: etl_week
    column: stat_week_date
    period: W
""",
            _NO_PARTITION,
            {
                "table": "ads_weekly",
                "field": "week_start",
                "message": (
                    "project verification.week_start is required for W periods"
                ),
            },
        ),
    ],
    ids=("partial-slice", "weekly-without-week-start"),
)
def test_build_verification_plan_blocks_invalid_slice_metadata(
    tmp_path,
    monkeypatch,
    table_name,
    model_yaml,
    partition,
    expected_error,
):
    plan = _build_single_anchor_plan(
        tmp_path,
        monkeypatch,
        table_name,
        model_yaml,
        task_sql="INSERT INTO demo_dm.{table_name} SELECT @etl_date;",
        partition=partition,
    )

    assert plan["verification"]["data_anchor_status"] == "blocked"
    assert plan["verification"]["metadata_errors"] == [expected_error]
    assert plan["verification"]["checks"] == []

    config.clear_model_metadata_cache()


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
            "changed_assets": {
                "task_jobs": ["dwd_order"],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dwd_order"],
                "downstream_tables": ["dws_order", "ads_order"],
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
            },
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


def test_build_verification_plan_maps_output_tables_to_explicit_job_names(
    tmp_path, monkeypatch
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "models").mkdir()
    (project_dir / "mid" / "tasks").mkdir()
    for table_name, layer in [
        ("dwd_order", "DWD"),
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
    for job_name in ("Prepare_Sales", "Build_Report"):
        (project_dir / "mid" / "tasks" / f"{job_name}.sql").write_text(
            "SELECT 1;",
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
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "name": "ads_order",
                "full_name": "internal.demo_dm.ads_order",
                "dataset_type": "managed",
                "columns": [],
            },
            {
                "name": "dwd_order",
                "full_name": "internal.demo_dm.dwd_order",
                "dataset_type": "managed",
                "columns": [],
            },
        ],
        "jobs": [
            {
                "name": "Build_Report",
                "source_file": "mid/tasks/Build_Report.sql",
                "inputs": ["internal.demo_dm.dwd_order"],
                "outputs": ["internal.demo_dm.ads_order"],
            },
            {
                "name": "Prepare_Sales",
                "source_file": "mid/tasks/Prepare_Sales.sql",
                "inputs": [],
                "outputs": ["internal.demo_dm.dwd_order"],
            },
        ],
        "edges": [],
        "diagnostics": [],
    }

    plan = build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": ["prepare_sales"],
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": ["dwd_order", "prepare_sales"],
                "downstream_tables": ["ads_order"],
                "assessment_tables": ["dwd_order", "ads_order"],
                "assessment_tasks": ["prepare_sales", "build_report"],
                "anchor_tables": ["ads_order"],
            },
        },
        lineage_data=lineage_data,
    )

    assert [
        (job["job"], job["target"], job["layer"])
        for job in plan["jobs_to_run"]
    ] == [
        ("Prepare_Sales", "dwd_order", "DWD"),
        ("Build_Report", "ads_order", "ADS"),
    ]
    assert plan["execution_graph"] == {
        "format_version": 1,
        "project": "demo",
        "jobs": ["Prepare_Sales", "Build_Report"],
        "dependencies": {
            "Build_Report": ["Prepare_Sales"],
            "Prepare_Sales": [],
        },
    }

    config.clear_model_metadata_cache()


def test_explicit_job_mapping_preserves_qualified_dataset_identity(
    tmp_path, monkeypatch
):
    task_dir = tmp_path / "demo" / "mid" / "tasks"
    task_dir.mkdir(parents=True)
    for job_name in ("build_a", "build_b"):
        (task_dir / f"{job_name}.sql").write_text(
            "SELECT 1;", encoding="utf-8"
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo",
            "db": "db_a",
            "qa_db": "db_a_qa",
            "catalog": "internal",
        },
    )
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "full_name": "internal.db_a.report",
                "dataset_type": "managed",
            },
            {
                "full_name": "internal.db_b.report",
                "dataset_type": "managed",
            },
        ],
        "jobs": [
            {
                "name": "build_a",
                "outputs": ["internal.db_a.report"],
            },
            {
                "name": "build_b",
                "outputs": ["internal.db_b.report"],
            },
        ],
    }

    entries = verification_plan_module._explicit_job_entries(
        "demo",
        {"internal.db_b.report"},
        lineage_data,
    )

    assert set(entries) == {"build_b"}


def test_schedule_writer_mapping_ignores_full_refresh_companion():
    lineage_data = {
        "jobs": [
            {
                "name": "build_sales",
                "outputs": ["internal.shop_dm.sales"],
            },
            {
                "name": "build_sales_full_refresh",
                "outputs": ["internal.shop_dm.sales"],
            },
        ]
    }
    schedule = ScheduleGraph("shop", ["build_sales"], {})

    writers = verification_plan_module._lineage_writer_jobs_for_tables(
        "shop",
        lineage_data,
        {"sales"},
        schedule,
    )

    assert writers == {"build_sales"}


def test_lineage_execution_windows_apply_to_all_writers(monkeypatch):
    jobs = [
        {"job": "write_even", "target": "shared_daily"},
        {"job": "write_odd", "target": "shared_daily"},
    ]
    monkeypatch.setattr(
        verification_plan_module,
        "_table_execution_slice_metadata",
        lambda *_args: {
            "param": "etl_date",
            "time_column": "stat_date",
            "time_period": "D",
        },
    )

    verification_plan_module._apply_execution_values_by_lineage(
        "shop",
        jobs,
        [
            {
                "table": "shared_daily",
                "time_period": "D",
                "start": date(2024, 6, 15),
                "end_exclusive": date(2024, 6, 16),
            }
        ],
        [],
        {"tables": [], "jobs": [], "edges": []},
    )

    assert [job["execution_values"] for job in jobs] == [
        ["2024-06-15"],
        ["2024-06-15"],
    ]


def test_explicit_job_mapping_rejects_multiple_managed_targets(
    tmp_path, monkeypatch
):
    task_dir = tmp_path / "demo" / "mid" / "tasks"
    task_dir.mkdir(parents=True)
    (task_dir / "multi_output.sql").write_text("SELECT 1;", encoding="utf-8")
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
    lineage_data = {
        "format_version": 2,
        "tables": [
            {
                "full_name": "internal.demo_dm.output_a",
                "dataset_type": "managed",
            },
            {
                "full_name": "internal.demo_dm.output_b",
                "dataset_type": "managed",
            },
        ],
        "jobs": [
            {
                "name": "multi_output",
                "outputs": [
                    "internal.demo_dm.output_a",
                    "internal.demo_dm.output_b",
                ],
            }
        ],
    }

    with pytest.raises(ValueError, match="multiple managed outputs"):
        verification_plan_module._explicit_job_entries(
            "demo",
            {"multi_output"},
            lineage_data,
        )

    with pytest.raises(ValueError, match="multiple managed outputs"):
        verification_plan_module._explicit_job_entries(
            "demo",
            {"internal.demo_dm.output_a"},
            lineage_data,
        )


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


def _semantic_record(table, mode, *, source="automatic", **extra):
    record = {
        "table_id": f"id-{table}",
        "declared_mode": None,
        "automatic_mode": "equivalent" if mode == "equivalent" else None,
        "resolved_mode": mode,
        "resolved_source": source,
        "local_change_fingerprint": f"sha256:local-{table}",
        "semantic_context_fingerprint": f"sha256:context-{table}",
        "upstream_context": [],
        "evidence": [],
        "prod_table": table,
        "qa_table": table,
        "column_mapping": [],
        "compare_blocker": None,
    }
    record.update(extra)
    return record


def _build_semantic_target_plan(
    tmp_path,
    monkeypatch,
    *,
    direct_tables,
    all_tables,
    edges,
    resolution,
):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "models").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir()
    for table in all_tables:
        (project_dir / "mid" / "models" / f"{table}.yaml").write_text(
            f"version: 2\nname: {table}\nlayer: DWS\n",
            encoding="utf-8",
        )
        (project_dir / "mid" / "tasks" / f"{table}.sql").write_text(
            f"INSERT INTO demo_dm.{table} SELECT 1;\n",
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
    downstream = sorted(set(all_tables) - set(direct_tables))
    lineage_edges = [
        {
            "source": {"type": "column", "id": f"{source}.id"},
            "target": {"type": "column", "id": f"{target}.id"},
        }
        for source, target in edges
    ]
    for table in direct_tables:
        if not any(target == table for _source, target in edges):
            lineage_edges.append(
                {
                    "source": {"type": "column", "id": "ods_source.id"},
                    "target": {"type": "column", "id": f"{table}.id"},
                }
            )
    return build_verification_plan(
        "demo",
        {
            "changed_assets": {
                "task_jobs": list(direct_tables),
                "ddl_tables": [],
                "model_tables": [],
                "config_files": [],
            },
            "affected_scope": {
                "direct_tables": list(direct_tables),
                "downstream_tables": downstream,
                "assessment_tables": list(all_tables),
                "assessment_tasks": list(all_tables),
                "anchor_tables": downstream,
            },
        },
        lineage_data={"edges": lineage_edges},
        semantic_resolution=resolution,
    )


def test_semantic_equivalent_direct_table_stops_unchanged_downstream_jobs(
    tmp_path, monkeypatch
):
    target_semantics = {
        "dws_store_sales_daily": _semantic_record(
            "dws_store_sales_daily", "equivalent"
        ),
        "ads_store_performance": _semantic_record(
            "ads_store_performance", "equivalent"
        ),
        "dim_store_metric_snapshot": _semantic_record(
            "dim_store_metric_snapshot", "equivalent"
        ),
    }
    resolution = SemanticResolution(
        target_semantics=target_semantics,
        boundaries={
            "authority": ["dws_store_sales_daily"],
            "observational": [],
        },
        selected_tables=("dws_store_sales_daily",),
        warnings=(),
        inherited_declarations={},
    )

    plan = _build_semantic_target_plan(
        tmp_path,
        monkeypatch,
        direct_tables=["dws_store_sales_daily"],
        all_tables=list(target_semantics),
        edges=[
            ("dws_store_sales_daily", "ads_store_performance"),
            ("dws_store_sales_daily", "dim_store_metric_snapshot"),
        ],
        resolution=resolution,
    )

    assert [job["job"] for job in plan["jobs_to_run"]] == [
        "dws_store_sales_daily"
    ]
    assert plan["verification"]["anchor_tables"] == ["dws_store_sales_daily"]
    assert {check["table"] for check in plan["verification"]["checks"]} == {
        "dws_store_sales_daily"
    }
    assert plan["verification"]["target_semantics"] == target_semantics


def test_semantic_unknown_path_uses_observational_leaf(tmp_path, monkeypatch):
    warning = {
        "type": "unknown_table_semantics",
        "table": "dws_sales",
        "message": "risk",
    }
    target_semantics = {
        "dws_sales": _semantic_record(
            "dws_sales", "unknown", source="default_unknown"
        ),
        "ads_sales": _semantic_record(
            "ads_sales", "unknown", source="upstream_propagation"
        ),
    }
    resolution = SemanticResolution(
        target_semantics=target_semantics,
        boundaries={"authority": [], "observational": ["ads_sales"]},
        selected_tables=("dws_sales", "ads_sales"),
        warnings=(warning,),
        inherited_declarations={},
    )

    plan = _build_semantic_target_plan(
        tmp_path,
        monkeypatch,
        direct_tables=["dws_sales"],
        all_tables=list(target_semantics),
        edges=[("dws_sales", "ads_sales")],
        resolution=resolution,
    )

    assert [job["job"] for job in plan["jobs_to_run"]] == [
        "dws_sales",
        "ads_sales",
    ]
    assert plan["verification"]["anchor_tables"] == ["ads_sales"]
    assert {check["table"] for check in plan["verification"]["checks"]} == {
        "ads_sales"
    }
    assert warning in plan["verification"]["warnings"]


def test_semantic_rename_checks_keep_prod_qa_and_column_mapping(
    tmp_path, monkeypatch
):
    column_mapping = [
        {
            "column_id": COLUMN_ID,
            "prod": "store_name",
            "qa": "STORE_NAME",
        }
    ]
    target_semantics = {
        "dim_store": _semantic_record(
            "dim_store",
            "equivalent",
            prod_table="dwd_store",
            qa_table="dim_store",
            column_mapping=column_mapping,
        )
    }
    resolution = SemanticResolution(
        target_semantics=target_semantics,
        boundaries={"authority": ["dim_store"], "observational": []},
        selected_tables=("dim_store",),
        warnings=(),
        inherited_declarations={},
    )

    plan = _build_semantic_target_plan(
        tmp_path,
        monkeypatch,
        direct_tables=["dim_store"],
        all_tables=["dim_store"],
        edges=[],
        resolution=resolution,
    )

    assert plan["verification"]["checks"] == [
        _check_group(
            "dim_store",
            prod_table="dwd_store",
            qa_table="dim_store",
            column_mapping=column_mapping,
        )
    ]


def test_equivalent_boundary_with_incomplete_mapping_is_blocked(
    tmp_path, monkeypatch
):
    target_semantics = {
        "dim_store": _semantic_record(
            "dim_store",
            "equivalent",
            compare_blocker="complete stable column identity is required",
        )
    }
    resolution = SemanticResolution(
        target_semantics=target_semantics,
        boundaries={"authority": ["dim_store"], "observational": []},
        selected_tables=("dim_store",),
        warnings=(),
        inherited_declarations={},
    )

    plan = _build_semantic_target_plan(
        tmp_path,
        monkeypatch,
        direct_tables=["dim_store"],
        all_tables=["dim_store"],
        edges=[],
        resolution=resolution,
    )

    assert plan["verification"]["checks"] == []
    assert plan["verification"]["data_anchor_status"] == "blocked"
    assert plan["verification"]["metadata_errors"] == [
        {
            "table": "dim_store",
            "field": "schema_identity",
            "message": "complete stable column identity is required",
        }
    ]
