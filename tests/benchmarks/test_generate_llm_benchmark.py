import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from benchmarks.table_inspector_layer.run import (
    TempProject,
    _llm_layers,
    _summarize_project,
    _table_mapping,
    build_temp_project,
    run_benchmark,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    TableInspectResult,
)
from dw_refactor_agent.lineage.view import LineageView

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_yaml(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _create_demo_project(root):
    source = root / "warehouses" / "demo"
    _write_yaml(
        source / "warehouse.yaml",
        {
            "name": "demo",
            "catalog": "internal",
            "database": "demo_dm",
            "qa_database": "demo_dm_qa",
            "lineage_database": "demo_lineage",
            "naming_config": "naming_config.yaml",
            "default_dialect": "doris",
            "ods_source_catalog_dialects": {"internal": "doris"},
        },
    )
    _write_text(source / "naming_config.yaml", "version: 1")
    _write_yaml(
        source / "business_taxonomy.yaml",
        {
            "version": 1,
            "project": "demo",
            "project_context": "Retail order analytics.",
            "data_domains": [{"id": "01", "code": "ORDER", "name": "Order"}],
            "business_areas": [
                {"id": "SALES", "code": "SALES", "name": "Sales"}
            ],
        },
    )
    _write_yaml(
        source / "business_processes.yaml",
        {
            "version": 1,
            "project": "demo",
            "business_processes": [
                {"code": "ORDER_SALES", "name": "Order Sales"}
            ],
        },
    )
    _write_yaml(
        source / "semantic_subjects.yaml",
        {
            "version": 1,
            "project": "demo",
            "semantic_subjects": [{"code": "CUSTOMER", "name": "Customer"}],
        },
    )

    ddl_by_table = {
        "ods_order_event": "CREATE TABLE IF NOT EXISTS demo_dm.ods_order_event (order_id BIGINT COMMENT 'ODS 原始层订单') ENGINE=OLAP DUPLICATE KEY(order_id) DISTRIBUTED BY HASH(order_id) BUCKETS 1 PROPERTIES ('replication_num'='1');",
        "dwd_order_detail": "CREATE TABLE IF NOT EXISTS demo_dm.dwd_order_detail (order_id BIGINT COMMENT 'DWD 明细层订单') ENGINE=OLAP DUPLICATE KEY(order_id) DISTRIBUTED BY HASH(order_id) BUCKETS 1 PROPERTIES ('replication_num'='1');",
        "dws_order_summary": "CREATE TABLE IF NOT EXISTS demo_dm.dws_order_summary (stat_date DATE COMMENT 'DWS 汇总层', order_count BIGINT COMMENT '订单数') ENGINE=OLAP DUPLICATE KEY(stat_date) DISTRIBUTED BY HASH(stat_date) BUCKETS 1 PROPERTIES ('replication_num'='1');",
        "dim_customer_profile": "CREATE TABLE IF NOT EXISTS demo_dm.dim_customer_profile (customer_id BIGINT COMMENT 'DIM 维度层') ENGINE=OLAP DUPLICATE KEY(customer_id) DISTRIBUTED BY HASH(customer_id) BUCKETS 1 PROPERTIES ('replication_num'='1');",
        "ads_order_dashboard": "CREATE TABLE IF NOT EXISTS demo_dm.ads_order_dashboard (stat_date DATE COMMENT 'ADS 应用层') ENGINE=OLAP DUPLICATE KEY(stat_date) DISTRIBUTED BY HASH(stat_date) BUCKETS 1 PROPERTIES ('replication_num'='1');",
    }
    _write_text(
        source
        / "ods"
        / "ddl"
        / "internal"
        / "demo_dm"
        / "ods_order_event.sql",
        ddl_by_table["ods_order_event"],
    )
    for table in (
        "dwd_order_detail",
        "dws_order_summary",
        "dim_customer_profile",
    ):
        _write_text(
            source / "mid" / "ddl" / f"{table}.sql", ddl_by_table[table]
        )
    _write_text(
        source / "ads" / "ddl" / "ads_order_dashboard.sql",
        ddl_by_table["ads_order_dashboard"],
    )

    _write_text(
        source / "mid" / "tasks" / "dwd_order_detail.sql",
        """
        -- DWD 明细层 task
        TRUNCATE TABLE demo_dm.dwd_order_detail;
        INSERT INTO demo_dm.dwd_order_detail
        SELECT order_id FROM demo_dm.ods_order_event;
        """,
    )
    _write_text(
        source / "mid" / "tasks" / "dws_order_summary.sql",
        """
        SET @etl_date = COALESCE(@etl_date, CURDATE());
        DELETE FROM demo_dm.dws_order_summary
        WHERE stat_date = CAST(@etl_date AS DATE);
        INSERT INTO demo_dm.dws_order_summary
        SELECT @etl_date, COUNT(*) FROM demo_dm.dwd_order_detail;
        """,
    )
    _write_text(
        source
        / "mid"
        / "tasks"
        / "full_refresh"
        / "dws_order_summary_full_refresh.sql",
        """
        -- DWS full refresh
        INSERT INTO demo_dm.dws_order_summary
        SELECT CURRENT_DATE, COUNT(*) FROM demo_dm.dwd_order_detail;
        """,
    )
    _write_text(
        source / "mid" / "tasks" / "dim_customer_profile.sql",
        """
        TRUNCATE TABLE demo_dm.dim_customer_profile;
        INSERT INTO demo_dm.dim_customer_profile
        SELECT order_id FROM demo_dm.ods_order_event;
        """,
    )
    _write_text(
        source / "ads" / "tasks" / "ads_order_dashboard.sql",
        """
        TRUNCATE TABLE demo_dm.ads_order_dashboard;
        INSERT INTO demo_dm.ads_order_dashboard
        SELECT stat_date FROM demo_dm.dws_order_summary;
        """,
    )

    model_rows = {
        "ods_order_event": ("ODS", "other"),
        "dwd_order_detail": ("DWD", "fact"),
        "dws_order_summary": ("DWS", "fact"),
        "dim_customer_profile": ("DIM", "dimension"),
        "ads_order_dashboard": ("ADS", "other"),
    }
    _write_yaml(
        source
        / "ods"
        / "models"
        / "internal"
        / "demo_dm"
        / "ods_order_event.yaml",
        {
            "version": 2,
            "name": "ods_order_event",
            "layer": "ODS",
            "table_type": "other",
        },
    )
    for table, (layer, table_type) in model_rows.items():
        if layer in {"ODS", "ADS"}:
            continue
        _write_yaml(
            source / "mid" / "models" / f"{table}.yaml",
            {
                "version": 2,
                "name": table,
                "layer": layer,
                "table_type": table_type,
            },
        )
    _write_yaml(
        source / "ads" / "models" / "ads_order_dashboard.yaml",
        {
            "version": 2,
            "name": "ads_order_dashboard",
            "layer": "ADS",
            "table_type": "other",
        },
    )
    return source


def test_build_temp_project_strips_layer_hints_and_seeds_empty_catalog(
    tmp_path,
):
    source_root = tmp_path / "source"
    _create_demo_project(source_root)

    temp_project = build_temp_project(
        "demo",
        "demo_generate_llm_benchmark",
        tmp_path / "assets",
        source_root=source_root,
    )

    target = temp_project.target_dir
    assert (target / "warehouse.yaml").exists()
    assert (target / "naming_config.yaml").exists()

    taxonomy = yaml.safe_load(
        (target / "business_taxonomy.yaml").read_text(encoding="utf-8")
    )
    assert taxonomy["project"] == "demo_generate_llm_benchmark"
    assert taxonomy["data_domains"][0]["code"] == "ORDER"
    assert "project_context" not in taxonomy
    assert "Retail order analytics" not in (
        target / "business_taxonomy.yaml"
    ).read_text(encoding="utf-8")

    processes = yaml.safe_load(
        (target / "business_processes.yaml").read_text(encoding="utf-8")
    )
    subjects = yaml.safe_load(
        (target / "semantic_subjects.yaml").read_text(encoding="utf-8")
    )
    assert processes["business_processes"] == []
    assert subjects["semantic_subjects"] == []

    mid_ddl = target / "mid" / "ddl" / "order_detail.sql"
    mid_task = target / "mid" / "tasks" / "order_detail.sql"
    full_refresh = (
        target
        / "mid"
        / "tasks"
        / "full_refresh"
        / "order_summary_full_refresh.sql"
    )
    assert mid_ddl.exists()
    assert mid_task.exists()
    assert full_refresh.exists()

    rewritten = mid_ddl.read_text(encoding="utf-8") + mid_task.read_text(
        encoding="utf-8"
    )
    assert "dwd_order_detail" not in rewritten
    assert "demo_dm" not in rewritten
    assert "COMMENT" not in rewritten.upper()
    assert "--" not in rewritten
    assert "DWD" not in rewritten
    assert "明细层" not in rewritten
    assert "order_detail" in rewritten


def test_table_mapping_salts_prefix_collisions():
    paths = [
        Path("dim_customer_profile.sql"),
        Path("dwd_customer_profile.sql"),
    ]
    first = _table_mapping(paths, alias_salt=b"a" * 32)
    second = _table_mapping(paths, alias_salt=b"b" * 32)
    first_aliases = set(first.values())

    assert len(first_aliases) == 2
    assert all(
        alias.startswith("customer_profile_") for alias in first_aliases
    )
    assert set(second.values()).isdisjoint(first_aliases)


def test_build_temp_project_rewrites_mixed_case_asset_identifiers(tmp_path):
    source_root = tmp_path / "source"
    source = _create_demo_project(source_root)
    ddl_path = source / "mid" / "ddl" / "dwd_order_detail.sql"
    task_path = source / "mid" / "tasks" / "dwd_order_detail.sql"
    ddl_path.rename(ddl_path.with_name("DWD_ORDER_DETAIL.sql"))
    task_path.rename(task_path.with_name("DWD_ORDER_DETAIL.sql"))

    temp_project = build_temp_project(
        "demo",
        "demo_generate_llm_benchmark",
        tmp_path / "assets",
        source_root=source_root,
        alias_salt=b"mixed-case-test" * 2,
    )
    rewritten_ddl = (
        temp_project.target_dir / "mid" / "ddl" / "order_detail.sql"
    ).read_text(encoding="utf-8")
    rewritten_task = (
        temp_project.target_dir / "mid" / "tasks" / "order_detail.sql"
    ).read_text(encoding="utf-8")

    assert temp_project.table_mapping["DWD_ORDER_DETAIL"] == "order_detail"
    assert temp_project.expected_by_target["order_detail"]["layer"] == "DWD"
    assert "dwd_order_detail" not in rewritten_ddl.casefold()
    assert "dwd_order_detail" not in rewritten_task.casefold()
    assert "order_detail" in rewritten_ddl.casefold()
    assert "order_event" in rewritten_task.casefold()


def test_run_benchmark_prefixless_mid_assets_enter_llm_contexts(
    tmp_path, monkeypatch
):
    import benchmarks.table_inspector_layer.run as benchmark_module
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    source_root = tmp_path / "source"
    _create_demo_project(source_root)
    seen_contexts = []
    inspector_parallelism = []
    lineage_parallelism = []
    real_write_lineage = benchmark_module._write_extracted_lineage

    def tracking_write_lineage(temp_project, *, parallelism):
        lineage_parallelism.append(parallelism)
        return real_write_lineage(temp_project, parallelism=parallelism)

    class FakeInspector:
        def __init__(self, *args, **kwargs):
            self.progress_callback = None
            inspector_parallelism.append(kwargs["parallelism"])

        def inspect_batch(self, contexts):
            seen_contexts.extend(
                (ctx.table_name, ctx.layer, ctx.expose_layer_hints)
                for ctx in contexts
            )
            results = []
            for ctx in contexts:
                if ctx.table_name == "customer_profile":
                    inferred_layer = "DIM"
                    table_type = "dimension"
                    entities = [
                        {
                            "code": "CUSTOMER",
                            "type": "primary",
                            "name": "Customer",
                            "key_columns": ["customer_id"],
                        }
                    ]
                    columns = None
                    grain = None
                elif ctx.table_name == "order_summary":
                    inferred_layer = "DWS"
                    table_type = "fact"
                    entities = []
                    columns = {
                        "atomic_metrics": [],
                        "derived_metrics": [
                            {
                                "name": "order_count",
                                "data_type": "BIGINT",
                                "business_process": "ORDER_SALES",
                            }
                        ],
                        "calculated_metrics": [],
                        "dimensions": [
                            {"name": "stat_date", "data_type": "DATE"}
                        ],
                        "others": [],
                    }
                    grain = {
                        "entities": [],
                        "time_column": "stat_date",
                        "time_period": "D",
                    }
                else:
                    inferred_layer = "DWD"
                    table_type = "fact"
                    entities = []
                    grain = None
                    columns = {
                        "atomic_metrics": [
                            {
                                "name": "order_id",
                                "data_type": "BIGINT",
                                "business_process": "ORDER_SALES",
                            }
                        ],
                        "derived_metrics": [],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    }
                results.append(
                    TableInspectResult(
                        table_name=ctx.table_name,
                        declared_layer=ctx.layer,
                        inferred_layer=inferred_layer,
                        table_type=table_type,
                        confidence=0.9,
                        reasoning_steps=[],
                        columns=columns
                        or {
                            "atomic_metrics": [],
                            "derived_metrics": [],
                            "calculated_metrics": [],
                            "dimensions": [],
                            "others": [],
                        },
                        entities=entities,
                        grain=grain or {},
                    )
                )
            return results

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)
    monkeypatch.setattr(
        benchmark_module,
        "_write_extracted_lineage",
        tracking_write_lineage,
    )
    output = tmp_path / "report.json"

    report = run_benchmark(
        projects=["demo"],
        api_key="fake-key",
        model="fake-model",
        base_url="https://api.deepseek.com",
        parallelism=8,
        max_retries=1,
        request_timeout=5,
        output_path=output,
        asset_dir=tmp_path / "assets",
        source_root=source_root,
    )

    assert report["benchmark"] == "generate_llm_cold_start"
    assert report["base_url"] == "https://api.deepseek.com/chat/completions"
    assert report["layer_hints_visible_to_llm"] is False
    assert report["parallelism"] == 8
    assert lineage_parallelism == [1]
    assert inspector_parallelism == [8]
    assert "combined_final_accuracy" not in report
    assert report["combined_llm_middle_accuracy"] == 1.0
    assert report["combined_post_retry_middle_accuracy"] == 1.0
    assert report["total_catalog_change_count"] == 2
    assert report["total_business_process_count"] == 1
    assert report["total_semantic_subject_count"] == 1
    assert report["published_project_count"] == 1
    assert report["blocked_project_count"] == 0
    assert set(seen_contexts) == {
        ("customer_profile", "DWD", False),
        ("order_detail", "DWD", False),
        ("order_summary", "DWD", False),
    }
    project = report["projects"][0]
    target_project = project["target_project"]
    assert target_project.startswith("generate_llm_benchmark_")
    assert "demo" not in target_project
    lineage_path = (
        tmp_path
        / "assets"
        / "warehouses"
        / target_project
        / "artifacts"
        / "lineage"
        / "lineage_data.json"
    )
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    upstream, _downstream = LineageView.from_data(
        "", lineage
    ).asset_table_graph()
    assert upstream["order_detail"] == {"order_event"}
    assert upstream["order_dashboard"] == {"order_summary"}
    assert project["source_project"] == "demo"
    assert project["table_count"] == 5
    assert project["middle_table_count"] == 3
    assert "final_accuracy" not in project
    assert project["llm_middle_accuracy"] == 1.0
    assert project["post_retry_middle_accuracy"] == 1.0
    assert project["metric_count"] == 2
    assert project["entity_table_count"] == 1
    assert project["grain_table_count"] == 1
    assert project["publication_status"] == "published"
    assert project["published"] is True
    assert project["publication_error_count"] == 0
    assert project["publication_errors"] == []
    assert project["catalog_summary"]["business_process_overlap_count"] == 1
    assert project["catalog_summary"]["semantic_subject_overlap_count"] == 1
    assert project["final_layer_counts"] == {
        "ADS": 1,
        "DIM": 1,
        "DWD": 1,
        "DWS": 1,
        "ODS": 1,
    }
    assert project["mismatches"] == []
    assert project["first_attempt_mismatches"] == []
    assert project["post_retry_mismatches"] == []
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_llm_layers_use_raw_inspection_results_only():
    result = {
        "llm_result": {
            "model_updates": [
                {
                    "table": "order_summary",
                    "layer": "DWS",
                    "table_type": "fact",
                }
            ],
            "tables": [
                {
                    "table_name": "order_summary",
                    "first_attempt_inferred_layer": "DWD",
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                }
            ],
        }
    }

    assert _llm_layers(result) == {"order_summary": "DIM"}
    assert _llm_layers(result, "first_attempt_inferred_layer") == {
        "order_summary": "DWD"
    }


def test_project_summary_records_post_retry_only_mismatch(tmp_path):
    _write_yaml(
        tmp_path / "business_processes.yaml",
        {
            "business_processes": [
                {"code": "EXISTING"},
            ]
        },
    )
    temp_project = TempProject(
        source_project="demo",
        target_project="opaque",
        source_dir=tmp_path,
        target_dir=tmp_path,
        database="demo",
        table_mapping={"sales_summary": "opaque_summary"},
        expected_by_source={
            "sales_summary": {"layer": "DWS", "table_type": "fact"}
        },
        expected_catalog={
            "business_processes": [],
            "semantic_subjects": [],
        },
    )
    result = {
        "model_updates": [
            {
                "table": "opaque_summary",
                "layer": "DWS",
                "table_type": "fact",
            }
        ],
        "candidate_models": {
            "opaque_summary": {
                "name": "opaque_summary",
                "layer": "DWS",
                "table_type": "fact",
                "derived_metrics": [{"name": "order_count"}],
                "entities": [
                    {
                        "code": "STORE",
                        "type": "foreign",
                        "key_columns": ["store_id"],
                    }
                ],
                "grain": {
                    "entities": ["STORE"],
                    "time_column": "stat_date",
                    "time_period": "D",
                },
            }
        },
        "planned_catalog_updates": [
            {
                "section": "business_processes",
                "action": "add",
                "code": "ORDER",
                "entry": {"code": "ORDER"},
            }
        ],
        "llm_result": {
            "tables": [
                {
                    "table_name": "opaque_summary",
                    "first_attempt_inferred_layer": "DWS",
                    "inferred_layer": "DWS",
                    "status": "blocked",
                    "columns": {
                        "atomic_metrics": [],
                        "derived_metrics": [{"name": "order_count"}],
                        "calculated_metrics": [],
                    },
                    "entities": [
                        {
                            "code": "STORE",
                            "type": "foreign",
                            "key_columns": ["store_id"],
                        }
                    ],
                    "grain": {
                        "entities": ["STORE"],
                        "time_column": "stat_date",
                        "time_period": "D",
                    },
                    "validation": {
                        METRIC_CONTEXT_REINSPECTION_ERROR_KEY: [
                            "upstream metric context reinspection failed"
                        ]
                    },
                }
            ]
        },
        "publication": {
            "status": "blocked",
            "published": False,
            "validation": {
                "error_count": 1,
                "errors": [
                    {
                        "type": "llm_inspection_blocked",
                        "table": "opaque_summary",
                    }
                ],
            },
        },
    }

    summary = _summarize_project(temp_project, result=result, dry_run=True)

    assert summary["first_attempt_mismatches"] == []
    assert summary["post_retry_mismatches"] == summary["mismatches"]
    assert summary["mismatches"][0]["source_table"] == "sales_summary"
    assert summary["mismatches"][0]["post_retry_middle_layer"] == "FAILED"
    assert summary["post_retry_middle_correct_count"] == 0
    assert summary["publication_status"] == "blocked"
    assert summary["published"] is False
    assert summary["publication_error_count"] == 1
    assert summary["publication_errors"] == [
        {
            "type": "llm_inspection_blocked",
            "table": "opaque_summary",
        }
    ]
    assert summary["candidate_model_summary"] == {
        "model_count": 1,
        "metric_count": 1,
        "metric_table_count": 1,
        "entity_table_count": 1,
        "grain_table_count": 1,
    }
    assert summary["published_model_summary"] == {
        "model_count": 0,
        "metric_count": 0,
        "metric_table_count": 0,
        "entity_table_count": 0,
        "grain_table_count": 0,
    }
    assert summary["inspection_summary"] == {
        "model_count": 1,
        "metric_count": 1,
        "metric_table_count": 1,
        "entity_table_count": 1,
        "grain_table_count": 1,
    }
    assert summary["metric_count"] == 1
    assert summary["catalog_summary"]["candidate"][
        "business_process_codes"
    ] == ["EXISTING", "ORDER"]
    assert summary["catalog_summary"]["published"][
        "business_process_codes"
    ] == ["EXISTING"]


def test_runner_script_help_works_without_pythonpath():
    env = dict(os.environ)
    env["PYTHONPATH"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "benchmarks/table_inspector_layer/run.py",
            "--help",
        ],
        cwd=str(PROJECT_ROOT),
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0
    assert (
        "generate --llm cold-start semantic metadata benchmark"
        in result.stdout
    )
