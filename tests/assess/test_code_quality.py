from assess.assessment_context import AssessmentContext
from assess.project_facts.asset_catalog import build_asset_catalog
from assess.scoring.task_sql_quality import score_code_quality


def _catalog_for_task(tmp_path, task_name, sql):
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / task_name).write_text(sql, encoding="utf-8")
    catalog = build_asset_catalog(
        [],
        None,
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    return AssessmentContext.from_facts(assets=catalog)


def _catalog_for_task_and_ddl(tmp_path, task_name, sql, ddl_files):
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "ddl").mkdir(parents=True)
    (project_dir / "tasks" / task_name).write_text(sql, encoding="utf-8")
    for ddl_name, ddl_sql in ddl_files.items():
        (project_dir / "ddl" / ddl_name).write_text(
            ddl_sql,
            encoding="utf-8",
        )
    catalog = build_asset_catalog(
        [],
        None,
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    return AssessmentContext.from_facts(assets=catalog)


def _issue_rule_ids(result):
    return {issue["rule_id"] for issue in result["issues"]}


def test_score_code_quality_accepts_named_and_dropped_temp_table(tmp_path):
    context = _catalog_for_task(
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

    result = score_code_quality(context)

    assert result["score"] == 100.0
    assert result["issues"] == []
    assert len(result["checks"]) == 4
    assert all(check["passed"] for check in result["checks"])


def test_score_code_quality_flags_bad_temp_name_and_missing_drop(tmp_path):
    context = _catalog_for_task(
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

    result = score_code_quality(context)

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
    context = _catalog_for_task(
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

    result = score_code_quality(context)

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
    context = _catalog_for_task(
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

    result = score_code_quality(context)

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
    context = _catalog_for_task(
        tmp_path,
        "dws_sales.sql",
        """
CREATE TABLE demo.dws_sales AS
SELECT order_id, amount
FROM demo.dwd_sales;
""",
    )

    result = score_code_quality(context)

    assert result["score"] == 100.0
    assert result["issues"] == []
    assert result["checks"][0]["rule_id"] == "CODE_NO_SELECT_STAR_IN_WRITE"


def test_score_code_quality_flags_cartesian_join_risks(tmp_path):
    context = _catalog_for_task(
        tmp_path,
        "dwd_order_customer.sql",
        """
INSERT INTO demo.dwd_order_customer
SELECT a.order_id, b.customer_name
FROM demo.dwd_order a
JOIN demo.dwd_customer b;

INSERT INTO demo.dwd_order_customer
SELECT a.order_id, b.store_name
FROM demo.dwd_order a
JOIN demo.dwd_store b ON 1 = 1;

INSERT INTO demo.dwd_order_customer
SELECT a.order_id, b.product_name
FROM demo.dwd_order a, demo.dwd_product b;
""",
    )

    result = score_code_quality(context)

    assert "CODE_CARTESIAN_JOIN_RISK" in _issue_rule_ids(result)
    failed = [
        check
        for check in result["checks"]
        if check["rule_id"] == "CODE_CARTESIAN_JOIN_RISK"
        and not check["passed"]
    ]
    assert len(failed) == 3
    assert {check["evidence"]["reason"] for check in failed} == {
        "missing_join_condition",
        "constant_join_condition",
        "comma_join",
    }


def test_score_code_quality_accepts_keyed_join_without_cartesian_risk(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "dwd_order_customer.sql",
        """
INSERT INTO demo.dwd_order_customer
SELECT a.order_id, b.customer_name
FROM demo.dwd_order a
JOIN demo.dwd_customer b ON a.customer_id = b.customer_id;
""",
    )

    result = score_code_quality(context)

    assert "CODE_CARTESIAN_JOIN_RISK" not in _issue_rule_ids(result)


def test_score_code_quality_accepts_multiple_ctes_without_cartesian_risk(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "ads_customer_rfm.sql",
        """
INSERT INTO demo.ads_customer_rfm
WITH rfm_base AS (
    SELECT
        customer_id,
        SUM(payment_amount) AS monetary
    FROM demo.dws_customer_order_summary
    GROUP BY customer_id
),
rfm_scored AS (
    SELECT
        customer_id,
        monetary,
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
    FROM rfm_base
)
SELECT
    customer_id,
    monetary,
    m_score
FROM rfm_scored;
""",
    )

    result = score_code_quality(context)

    assert "CODE_CARTESIAN_JOIN_RISK" not in _issue_rule_ids(result)


def test_score_code_quality_accepts_explicit_cross_join_without_cartesian_risk(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "dim_date.sql",
        """
INSERT INTO demo.dim_date
WITH date_spine AS (
    SELECT DATE_ADD(CAST('2010-01-01' AS DATE), INTERVAL (o.n + t.n * 10) DAY) AS date_day
    FROM (SELECT 0 AS n UNION ALL SELECT 1 AS n) o
    CROSS JOIN (SELECT 0 AS n UNION ALL SELECT 1 AS n) t
)
SELECT date_day
FROM date_spine;
""",
    )

    result = score_code_quality(context)

    assert "CODE_CARTESIAN_JOIN_RISK" not in _issue_rule_ids(result)


def test_score_code_quality_flags_dws_join_before_aggregation_fanout(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "dws_store_sales_daily.sql",
        """
INSERT INTO demo.dws_store_sales_daily
SELECT
    s.store_id,
    SUM(o.pay_amount) AS pay_amount
FROM demo.dwd_order_detail o
JOIN demo.dwd_store_tag s ON o.store_id = s.store_id
GROUP BY s.store_id;
""",
    )

    result = score_code_quality(context)

    assert "CODE_DWS_JOIN_BEFORE_AGGREGATION" in _issue_rule_ids(result)


def test_score_code_quality_accepts_dws_join_to_pre_aggregated_subquery(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "dws_account_daily_snapshot.sql",
        """
INSERT INTO demo.dws_account_daily_snapshot
WITH daily_snapshots AS (
    SELECT
        a.account_id,
        COALESCE(t.daily_transaction_count, 0) AS daily_transaction_count
    FROM demo.dwd_accounts a
    LEFT JOIN (
        SELECT
            account_id,
            COUNT(*) AS daily_transaction_count
        FROM demo.dwd_transactions
        GROUP BY account_id
    ) t ON a.account_id = t.account_id
)
SELECT account_id, daily_transaction_count
FROM daily_snapshots;
""",
    )

    result = score_code_quality(context)

    assert "CODE_DWS_JOIN_BEFORE_AGGREGATION" not in _issue_rule_ids(result)


def test_score_code_quality_accepts_dws_join_covering_right_unique_key(
    tmp_path,
):
    context = _catalog_for_task_and_ddl(
        tmp_path,
        "dws_promotion_effect_daily.sql",
        """
INSERT INTO demo.dws_promotion_effect_daily
SELECT
    od.promotion_id,
    od.order_date AS stat_date,
    MAX(p.promotion_name) AS promotion_name,
    SUM(od.subtotal) AS sale_amount
FROM demo.dwd_order_detail od
LEFT JOIN demo.dwd_promotion p
    ON od.promotion_id = p.promotion_id
   AND od.order_date = p.snapshot_date
GROUP BY od.promotion_id, od.order_date;
""",
        {
            "dwd_promotion.sql": """
CREATE TABLE demo.dwd_promotion (
    promotion_id BIGINT NOT NULL,
    snapshot_date DATE NOT NULL,
    promotion_name VARCHAR(128) NULL
) ENGINE=OLAP
UNIQUE KEY(promotion_id, snapshot_date)
DISTRIBUTED BY HASH(promotion_id) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
        },
    )

    result = score_code_quality(context)

    assert "CODE_DWS_JOIN_BEFORE_AGGREGATION" not in _issue_rule_ids(result)


def test_score_code_quality_flags_dws_join_partially_covering_unique_key(
    tmp_path,
):
    context = _catalog_for_task_and_ddl(
        tmp_path,
        "dws_promotion_effect_daily.sql",
        """
INSERT INTO demo.dws_promotion_effect_daily
SELECT
    od.promotion_id,
    od.order_date AS stat_date,
    MAX(p.promotion_name) AS promotion_name,
    SUM(od.subtotal) AS sale_amount
FROM demo.dwd_order_detail od
LEFT JOIN demo.dwd_promotion p
    ON od.promotion_id = p.promotion_id
GROUP BY od.promotion_id, od.order_date;
""",
        {
            "dwd_promotion.sql": """
CREATE TABLE demo.dwd_promotion (
    promotion_id BIGINT NOT NULL,
    snapshot_date DATE NOT NULL,
    promotion_name VARCHAR(128) NULL
) ENGINE=OLAP
UNIQUE KEY(promotion_id, snapshot_date)
DISTRIBUTED BY HASH(promotion_id) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
        },
    )

    result = score_code_quality(context)

    assert "CODE_DWS_JOIN_BEFORE_AGGREGATION" in _issue_rule_ids(result)


def test_score_code_quality_flags_function_wrapped_filter_column(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "dwd_order_detail.sql",
        """
INSERT INTO demo.dwd_order_detail
SELECT order_id, pay_amount
FROM demo.ods_order
WHERE DATE(pay_time) = @etl_date
  AND CAST(store_id AS VARCHAR) = '1001';
""",
    )

    result = score_code_quality(context)

    assert "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION" in _issue_rule_ids(result)
    failed = [
        check
        for check in result["checks"]
        if check["rule_id"] == "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION"
        and not check["passed"]
    ]
    assert len(failed) == 2


def test_score_code_quality_accepts_full_refresh_if_filter_predicate(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "dws_customer_order_summary.sql",
        """
INSERT INTO demo.dws_customer_order_summary
SELECT customer_id, SUM(payment_amount) AS payment_amount
FROM demo.dwd_order_detail
WHERE IF(@full_refresh = 1, 1=1, order_date = CAST(@etl_date AS DATE))
GROUP BY customer_id;
""",
    )

    result = score_code_quality(context)

    assert "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION" not in _issue_rule_ids(
        result
    )


def test_score_code_quality_accepts_generator_expression_filter(
    tmp_path,
):
    context = _catalog_for_task(
        tmp_path,
        "dim_date.sql",
        """
INSERT INTO demo.dim_date
WITH date_spine AS (
    SELECT DATE_ADD(CAST('2010-01-01' AS DATE), INTERVAL o.n DAY) AS date_day
    FROM (SELECT 0 AS n UNION ALL SELECT 1 AS n) o
    WHERE DATE_ADD(CAST('2010-01-01' AS DATE), INTERVAL o.n DAY) <= CAST('2030-12-31' AS DATE)
)
SELECT date_day
FROM date_spine;
""",
    )

    result = score_code_quality(context)

    assert "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION" not in _issue_rule_ids(
        result
    )


def test_score_code_quality_accepts_sargable_filter_columns(tmp_path):
    context = _catalog_for_task(
        tmp_path,
        "dwd_order_detail.sql",
        """
INSERT INTO demo.dwd_order_detail
SELECT order_id, pay_amount
FROM demo.ods_order
WHERE pay_time >= @etl_date
  AND pay_time < DATE_ADD(@etl_date, INTERVAL 1 DAY)
  AND store_id = 1001;
""",
    )

    result = score_code_quality(context)

    assert "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION" not in _issue_rule_ids(
        result
    )
