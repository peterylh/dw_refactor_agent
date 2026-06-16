from assess.assess_middle_layer import build_asset_catalog
from assess.code_quality import score_code_quality


def _catalog_for_task(tmp_path, task_name, sql):
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / task_name).write_text(sql, encoding="utf-8")
    return build_asset_catalog(
        [],
        None,
        project_dir,
        edges=[],
        indirect_edges=[],
    )


def _issue_rule_ids(result):
    return {issue["rule_id"] for issue in result["issues"]}


def test_score_code_quality_accepts_named_and_dropped_temp_table(tmp_path):
    catalog = _catalog_for_task(
        tmp_path,
        "dws_sales.sql",
        """
CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales;

INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.tmp_sales_stage;

DROP TABLE IF EXISTS demo.tmp_sales_stage;
""",
    )

    result = score_code_quality(catalog)

    assert result["score"] == 100.0
    assert result["issues"] == []
    assert len(result["checks"]) == 4
    assert all(check["passed"] for check in result["checks"])


def test_score_code_quality_flags_bad_temp_name_and_missing_drop(tmp_path):
    catalog = _catalog_for_task(
        tmp_path,
        "dws_sales.sql",
        """
CREATE TABLE demo.stage_sales AS
SELECT order_id, amount
FROM demo.dwd_sales;

INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.stage_sales;
""",
    )

    result = score_code_quality(catalog)

    assert result["score"] == 50.0
    assert _issue_rule_ids(result) == {
        "CODE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP",
        "CODE_TEMP_TABLE_DROPPED_IN_SAME_TASK",
    }
    assert {
        (item["target"]["name"], item["severity"]) for item in result["issues"]
    } == {
        ("stage_sales", "低"),
        ("stage_sales", "中"),
    }


def test_score_code_quality_requires_drop_after_create(tmp_path):
    catalog = _catalog_for_task(
        tmp_path,
        "dws_sales.sql",
        """
DROP TABLE IF EXISTS demo.tmp_sales_stage;

CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales;

INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.tmp_sales_stage;
""",
    )

    result = score_code_quality(catalog)

    assert result["score"] == 75.0
    assert result["issues"][0]["rule_id"] == (
        "CODE_TEMP_TABLE_DROPPED_IN_SAME_TASK"
    )
    assert result["issues"][0]["severity"] == "中"
    assert result["issues"][0]["remediation"]["strategy"] == (
        "drop_temp_table_after_use"
    )


def test_score_code_quality_flags_select_star_only_in_write_statements(
    tmp_path,
):
    catalog = _catalog_for_task(
        tmp_path,
        "dws_sales.sql",
        """
SELECT *
FROM demo.dwd_sales;

INSERT INTO demo.dws_sales
SELECT *
FROM demo.dwd_sales;
""",
    )

    result = score_code_quality(catalog)

    assert result["score"] == 0.0
    assert result["checks"] == [
        {
            "id": "code_quality.chk_001",
            "rule_id": "CODE_NO_SELECT_STAR_IN_WRITE",
            "target": {
                "type": "task",
                "name": "demo/tasks/dws_sales.sql",
            },
            "passed": False,
            "expected": "写入型语句显式列出字段",
            "actual": "写入 dws_sales 时使用 SELECT *",
            "evidence": {
                "file": "demo/tasks/dws_sales.sql",
                "table": "dws_sales",
            },
            "message": "写入型语句使用SELECT *，请显式列出字段",
        }
    ]
    assert result["issues"] == [
        {
            "id": "code_quality.iss_001",
            "severity": "高",
            "rule_id": "CODE_NO_SELECT_STAR_IN_WRITE",
            "target": {
                "type": "task",
                "name": "demo/tasks/dws_sales.sql",
            },
            "title": "写入型SQL使用SELECT *",
            "message": "写入型语句使用SELECT *，请显式列出字段",
            "remediation": {
                "summary": "将写入型SQL中的SELECT *改为显式字段列表",
                "strategy": "expand_select_star",
                "edit_scope": ["tasks"],
            },
            "check_ids": ["code_quality.chk_001"],
        }
    ]


def test_score_code_quality_ignores_task_target_create_table(tmp_path):
    catalog = _catalog_for_task(
        tmp_path,
        "dws_sales.sql",
        """
CREATE TABLE demo.dws_sales AS
SELECT order_id, amount
FROM demo.dwd_sales;
""",
    )

    result = score_code_quality(catalog)

    assert result["score"] == 100.0
    assert result["issues"] == []
    assert result["checks"][0]["rule_id"] == "CODE_NO_SELECT_STAR_IN_WRITE"
