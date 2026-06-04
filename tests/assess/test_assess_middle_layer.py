from config import load_naming_config, PROJECT_ROOT
from assess.assess_middle_layer import (
    ATOMIC_METRIC_RULE_NAME,
    DERIVED_METRIC_RULE_NAME,
    FILE_RULE_DDL,
    FILE_RULE_MODEL_NAME,
    FILE_RULE_MODEL_TABLE,
    FILE_RULE_TASK_LINEAGE,
    FILE_RULE_TASK_SQL,
    assess,
    generate_report,
    score_architecture_health,
    score_naming_conventions,
)
from assess.table_inspector import TableInspectResult


def test_assess_returns_raw_and_display_scores(monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project="shop")

    assert "architecture" in result
    assert result["weights"]["architecture"] == 0.25

    # 展示分 = 原始分 (取消展示分映射后)
    assert result["reuse"]["raw"] == result["reuse"]["display"]
    assert result["depth"]["raw"] == result["depth"]["display"]
    assert result["architecture"]["raw"] == result["architecture"]["display"]
    assert result["naming"]["raw"] == result["naming"]["display"]
    assert result["overall_display"] == result["overall_raw"]

    # sample: 4 张表, 1 条违规 (低权重=1), cap 后 = 1, 合规率 = (1 - 1/4) × 100 = 75
    assert result["architecture"]["raw"] == 75.0


def test_generate_report_contains_raw_and_display_scores(
        monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project="shop")
    report = generate_report(result, result["weights"], "shop")

    assert "总体评分(展示)" in report
    assert "总体评分(原始)" in report
    assert "【架构合理性】评分: 75.0" in report
    assert "Σ(每表 cap 后权重) = 1" in report


def test_assess_includes_atomic_metric_naming_summary(
        monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )
    monkeypatch.setattr(
        "config.load_model_metadata",
        lambda project: {
            "dwd_order_detail": {
                "atomic_metrics": ["PAY_AMT", "PAY_UNKNOWN"]
            }
        },
    )

    result = assess(project="shop")

    assert result["naming"]["rule_summary"][ATOMIC_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }


def test_score_architecture_health_penalizes_declared_table_type_mismatch(
        sample_lineage_data):
    result = score_architecture_health(
        sample_lineage_data["tables"],
        sample_lineage_data["edges"],
        sample_lineage_data["indirect_edges"],
        llm_results=[
            TableInspectResult(
                table_name="dws_store_sales_daily",
                declared_layer="DWS",
                inferred_layer="DWS",
                table_type="dimension",
                confidence=0.9,
                reasoning_steps=[],
            )
        ],
        model_metadata={
            "dws_store_sales_daily": {
                "table_type": "fact",
            }
        },
    )

    type_violations = [
        v for v in result["violations"]
        if v["description"].startswith("表类型配置疑似错误")
    ]
    assert type_violations == [{
        "source": "dws_store_sales_daily(fact)",
        "target": "dws_store_sales_daily(dimension)",
        "severity": "中",
        "weight": 2,
        "description": "表类型配置疑似错误(LLM): 配置类型=fact, 推断类型=dimension",
        "source_file": "",
        "source_type": "llm",
        "belongs_to": "dws_store_sales_daily",
    }]


def test_score_architecture_health_allows_ads_to_read_dim():
    tables = [
        {"name": "dim_customer", "layer": "DIM", "columns": []},
        {"name": "ads_customer_by_segment", "layer": "ADS", "columns": []},
    ]
    edges = [{
        "source": "dim_customer.customer_id",
        "target": "ads_customer_by_segment.customer_id",
        "source_file": "ads_customer_by_segment.sql",
    }]

    result = score_architecture_health(tables, edges, [])

    assert result["score"] == 100.0
    assert result["violations"] == []


def test_score_naming_conventions_checks_table_name_length():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [
        {"name": "M_WEMG_04_CHREM_DI", "layer": "DWD", "columns": []},
        {"name": "M_WEMG_04_CHREMEXTRALONGNAME_DI", "layer": "DWD", "columns": []},
    ]

    result = score_naming_conventions(tables, nc)

    assert result["rule_summary"]["表名长度 <= 30"] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["details"][1]["table_checks"]["violations"] == ["违反: 表名长度 <= 30"]


def test_score_naming_conventions_checks_project_file_names(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks" / "full_refresh").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    ddl = f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    ID BIGINT
) ENGINE=OLAP
DUPLICATE KEY(ID)
DISTRIBUTED BY HASH(ID) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
    (project_dir / "ddl" / f"{table_name}.sql").write_text(ddl)
    (project_dir / "models" / f"{table_name}.yaml").write_text(
        f"name: {table_name}\nlayer: DWD\n"
    )
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )
    full_refresh = project_dir / "tasks" / "full_refresh" / (
        f"{table_name}_full_refresh.sql"
    )
    full_refresh.write_text(f"INSERT INTO demo.{table_name} SELECT 1 AS ID;")

    tables = []
    edges = [
        {
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"{table_name}.sql",
        },
        {
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"full_refresh/{table_name}_full_refresh.sql",
        },
    ]

    result = score_naming_conventions(
        tables,
        nc,
        project_dir=project_dir,
        edges=edges,
        indirect_edges=[],
    )

    assert result["score"] == 100.0
    assert result["file_checks"] == {"passed": 7, "total": 7}
    assert result["file_details"] == []
    assert result["rule_summary"][FILE_RULE_DDL] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_TABLE] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_NAME] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 2,
        "total": 2,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 2,
        "total": 2,
        "pct": 100.0,
    }


def test_score_naming_conventions_flags_project_file_name_mismatches(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "models").mkdir()
    (project_dir / "tasks").mkdir()

    table_name = "M_WEMG_04_CHREM_DI"
    ddl = f"""
CREATE TABLE IF NOT EXISTS demo.{table_name} (
    ID BIGINT
) ENGINE=OLAP
DUPLICATE KEY(ID)
DISTRIBUTED BY HASH(ID) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
    (project_dir / "ddl" / "wrong_ddl.sql").write_text(ddl)
    (project_dir / "models" / "wrong_model.yaml").write_text(
        f"name: {table_name}\nlayer: DWD\n"
    )
    (project_dir / "tasks" / "wrong_task.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )

    tables = [{"name": table_name, "layer": "DWD", "columns": []}]
    edges = [{
        "source": "ods_source.ID",
        "target": f"{table_name}.ID",
        "source_file": "wrong_task.sql",
    }]

    result = score_naming_conventions(
        tables,
        nc,
        project_dir=project_dir,
        edges=edges,
        indirect_edges=[],
    )

    assert result["score"] == 28.6
    assert result["file_checks"] == {"passed": 0, "total": 5}
    assert result["rule_summary"][FILE_RULE_DDL] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_TABLE] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_MODEL_NAME] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert {detail["rule"] for detail in result["file_details"]} == {
        FILE_RULE_DDL,
        FILE_RULE_MODEL_TABLE,
        FILE_RULE_MODEL_NAME,
        FILE_RULE_TASK_SQL,
        FILE_RULE_TASK_LINEAGE,
    }


def test_score_naming_conventions_flags_missing_task_lineage(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )

    result = score_naming_conventions(
        [],
        nc,
        project_dir=project_dir,
        edges=[],
        indirect_edges=[],
    )

    assert result["score"] == 50.0
    assert result["file_checks"] == {"passed": 1, "total": 2}
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["file_details"] == [{
        "file": "demo/tasks/M_WEMG_04_CHREM_DI.sql",
        "rule": FILE_RULE_TASK_LINEAGE,
        "expected": table_name,
        "actual": "未解析",
    }]


def test_score_naming_conventions_does_not_reuse_basename_lineage(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "tasks" / "archive").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"INSERT INTO demo.{table_name} SELECT 1 AS ID;"
    )
    archived_task = project_dir / "tasks" / "archive" / f"{table_name}.sql"
    archived_task.write_text(f"INSERT INTO demo.{table_name} SELECT 1 AS ID;")

    result = score_naming_conventions(
        [],
        nc,
        project_dir=project_dir,
        edges=[{
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"{table_name}.sql",
        }],
        indirect_edges=[],
    )

    assert result["file_checks"] == {"passed": 3, "total": 4}
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["file_details"] == [{
        "file": f"demo/tasks/archive/{table_name}.sql",
        "rule": FILE_RULE_TASK_LINEAGE,
        "expected": table_name,
        "actual": "未解析",
    }]


def test_score_naming_conventions_checks_extra_write_targets(tmp_path):
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)

    table_name = "M_WEMG_04_CHREM_DI"
    (project_dir / "tasks" / f"{table_name}.sql").write_text(
        f"""
TRUNCATE TABLE demo.WRONG_TARGET;
INSERT INTO demo.{table_name} SELECT 1 AS ID;
UPDATE demo.{table_name} SET ID = 1;
DELETE FROM demo.{table_name} WHERE ID = 1;
"""
    )

    result = score_naming_conventions(
        [],
        nc,
        project_dir=project_dir,
        edges=[{
            "source": "ods_source.ID",
            "target": f"{table_name}.ID",
            "source_file": f"{table_name}.sql",
        }],
        indirect_edges=[],
    )

    assert result["score"] == 50.0
    assert result["file_checks"] == {"passed": 1, "total": 2}
    assert result["rule_summary"][FILE_RULE_TASK_SQL] == {
        "pass_count": 0,
        "total": 1,
        "pct": 0.0,
    }
    assert result["rule_summary"][FILE_RULE_TASK_LINEAGE] == {
        "pass_count": 1,
        "total": 1,
        "pct": 100.0,
    }
    assert result["file_details"] == [{
        "file": f"demo/tasks/{table_name}.sql",
        "rule": FILE_RULE_TASK_SQL,
        "expected": table_name,
        "actual": f"{table_name}, WRONG_TARGET",
    }]


def test_score_naming_conventions_checks_atomic_metrics_from_models():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "atomic_metrics": ["PAY_AMT", "pay_amt", "PAY_UNKNOWN"]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][ATOMIC_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 3,
        "pct": 33.3,
    }
    assert result["details"][0]["atomic_metric_checks"] == {
        "passed": 1,
        "total": 3,
        "violations": ["PAY_UNKNOWN", "pay_amt"],
    }


def test_score_naming_conventions_checks_derived_metrics_from_models():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "derived_metrics": [
                "7D_OLD_CHREM_PAY_AMT",
                "30D_HIGH_NET_PAY_CNT",
                "OLD_7D_PAY_AMT",
                "7D_OL_PAY_AMT",
                "7D_OLD_PAY_UNKNOWN",
            ]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][DERIVED_METRIC_RULE_NAME] == {
        "pass_count": 2,
        "total": 5,
        "pct": 40.0,
    }
    assert result["details"][0]["derived_metric_checks"] == {
        "passed": 2,
        "total": 5,
        "violations": [
            "7D_OLD_PAY_UNKNOWN",
            "7D_OL_PAY_AMT",
            "OLD_7D_PAY_AMT",
        ],
    }


def test_score_naming_conventions_checks_default_enterprise_metric_bindings():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "atomic_metrics": ["PAY_AMT", "pay_amt"],
            "derived_metrics": ["7D_OLD_PAY_AMT", "transaction_count"],
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][ATOMIC_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["rule_summary"][DERIVED_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }


def test_score_naming_conventions_derived_metrics_follow_rule_config():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    nc.metric_rules["derived"][0]["nodes"][1]["repeat"]["min"] = 2
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "derived_metrics": [
                "7D_OLD_CHREM_PAY_AMT",
                "7D_OLD_PAY_AMT",
            ]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["rule_summary"][DERIVED_METRIC_RULE_NAME] == {
        "pass_count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert result["details"][0]["derived_metric_checks"] == {
        "passed": 1,
        "total": 2,
        "violations": ["7D_OLD_PAY_AMT"],
    }


def test_score_naming_conventions_does_not_double_check_derived_metric_columns():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [{"name": "7D_OLD_PAY_AMT"}],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "derived_metrics": ["7D_OLD_PAY_AMT"]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["details"][0]["column_checks"] == {
        "passed": 0,
        "total": 0,
        "violations": [],
    }
    assert result["details"][0]["derived_metric_checks"] == {
        "passed": 1,
        "total": 1,
        "violations": [],
    }
    assert result["details"][0]["score"] == 100.0


def test_score_naming_conventions_does_not_double_check_atomic_metric_columns():
    nc = load_naming_config(PROJECT_ROOT / "naming_config.yaml")
    tables = [{
        "name": "M_WEMG_04_CHREM_DI",
        "layer": "DWD",
        "columns": [{"name": "PAY_AMT"}],
    }]
    model_metadata = {
        "M_WEMG_04_CHREM_DI": {
            "atomic_metrics": ["PAY_AMT"]
        }
    }

    result = score_naming_conventions(tables, nc, model_metadata)

    assert result["details"][0]["column_checks"] == {
        "passed": 0,
        "total": 0,
        "violations": [],
    }
    assert result["details"][0]["atomic_metric_checks"] == {
        "passed": 1,
        "total": 1,
        "violations": [],
    }
    assert result["details"][0]["score"] == 100.0
