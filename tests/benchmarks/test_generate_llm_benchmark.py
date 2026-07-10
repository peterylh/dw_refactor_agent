import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from benchmarks.table_inspector_layer.run import (
    _llm_layers,
    build_temp_project,
    run_benchmark,
)
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
    build_prompt,
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
        "dws_order_summary": "CREATE TABLE IF NOT EXISTS demo_dm.dws_order_summary (stat_date DATE COMMENT 'DWS 汇总层') ENGINE=OLAP DUPLICATE KEY(stat_date) DISTRIBUTED BY HASH(stat_date) BUCKETS 1 PROPERTIES ('replication_num'='1');",
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
        INSERT INTO demo_dm.dwd_order_detail
        SELECT order_id FROM demo_dm.ods_order_event;
        """,
    )
    _write_text(
        source / "mid" / "tasks" / "dws_order_summary.sql",
        """
        INSERT INTO demo_dm.dws_order_summary
        SELECT CURRENT_DATE, COUNT(*) FROM demo_dm.dwd_order_detail;
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
        INSERT INTO demo_dm.dim_customer_profile
        SELECT order_id FROM demo_dm.ods_order_event;
        """,
    )
    _write_text(
        source / "ads" / "tasks" / "ads_order_dashboard.sql",
        """
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


def test_run_benchmark_prefixless_mid_assets_enter_llm_contexts(
    tmp_path, monkeypatch
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    source_root = tmp_path / "source"
    _create_demo_project(source_root)
    seen_contexts = []
    seen_prompts = {}

    class FakeInspector:
        def __init__(self, *args, **kwargs):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            seen_contexts.extend(
                (ctx.table_name, ctx.layer, ctx.expose_layer_hints)
                for ctx in contexts
            )
            seen_prompts.update(
                {ctx.table_name: build_prompt(ctx) for ctx in contexts}
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
                    columns = None
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
    output = tmp_path / "report.json"

    report = run_benchmark(
        projects=["demo"],
        api_key="fake-key",
        model="fake-model",
        base_url="https://api.deepseek.com",
        parallelism=1,
        max_retries=1,
        request_timeout=5,
        output_path=output,
        asset_dir=tmp_path / "assets",
        source_root=source_root,
    )

    assert report["benchmark"] == "generate_llm_cold_start"
    assert report["base_url"] == "https://api.deepseek.com/chat/completions"
    assert report["layer_hints_visible_to_llm"] is False
    assert "combined_final_accuracy" not in report
    assert report["combined_llm_middle_accuracy"] == 1.0
    assert report["total_catalog_change_count"] == 2
    assert report["total_business_process_count"] == 1
    assert report["total_semantic_subject_count"] == 1
    assert set(seen_contexts) == {
        ("customer_profile", "DWD", False),
        ("order_detail", "DWD", False),
        ("order_summary", "DWD", False),
    }
    assert "原始配置层级: 未提供" in seen_prompts["order_detail"]
    assert "上游表: order_event" in seen_prompts["order_detail"]
    assert "order_event(ODS)" not in seen_prompts["order_detail"]
    assert "下游表: order_dashboard" in seen_prompts["order_summary"]
    assert "order_dashboard(ADS)" not in seen_prompts["order_summary"]
    lineage_path = (
        tmp_path
        / "assets"
        / "warehouses"
        / "demo_generate_llm_benchmark"
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
    project = report["projects"][0]
    assert project["source_project"] == "demo"
    assert project["table_count"] == 5
    assert project["middle_table_count"] == 3
    assert "final_accuracy" not in project
    assert project["llm_middle_accuracy"] == 1.0
    assert project["metric_count"] == 1
    assert project["entity_table_count"] == 1
    assert project["grain_table_count"] == 1
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
                    "inferred_layer": "DIM",
                    "table_type": "dimension",
                }
            ],
        }
    }

    assert _llm_layers(result) == {"order_summary": "DIM"}


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
