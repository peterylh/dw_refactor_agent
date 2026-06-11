from assess.assess_middle_layer import build_asset_catalog
from assess.code_quality import (
    RULE_NO_SELECT_STAR_IN_WRITE,
    RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK,
    RULE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP,
    score_code_quality,
)


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
    assert result["passed"] == 4
    assert result["total"] == 4
    assert result["details"] == []


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
    assert {
        (item["table"], item["rule"])
        for item in result["details"]
    } == {
        ("stage_sales", RULE_TEMP_TABLE_NAME_HAS_TEMP_OR_TMP),
        ("stage_sales", RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK),
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
    assert result["details"] == [{
        "file": "demo/tasks/dws_sales.sql",
        "table": "tmp_sales_stage",
        "rule": RULE_TEMP_TABLE_DROPPED_IN_SAME_TASK,
        "message": "临时表未在同一作业后续DROP清理",
    }]


def test_score_code_quality_flags_select_star_only_in_write_statements(
        tmp_path):
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
    assert result["passed"] == 0
    assert result["total"] == 1
    assert result["details"] == [{
        "file": "demo/tasks/dws_sales.sql",
        "table": "dws_sales",
        "rule": RULE_NO_SELECT_STAR_IN_WRITE,
        "message": "写入型语句使用SELECT *，请显式列出字段",
    }]


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
    assert result["passed"] == 1
    assert result["total"] == 1
    assert result["details"] == []
