import pytest

import dw_refactor_agent.assessment.rules.definitions.task_sql_quality as task_sql_quality_defs
import dw_refactor_agent.assessment.rules.dimensions.task_sql_quality as task_sql_quality_dimension
from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    build_asset_catalog,
)
from dw_refactor_agent.assessment.rules.dimensions.task_sql_quality import (
    score_code_quality,
)
from dw_refactor_agent.config import PROJECT_CONFIG, PROJECT_ROOT


def _catalog_for_task(tmp_path, task_name, sql):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / task_name).write_text(
        sql, encoding="utf-8"
    )
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
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks" / task_name).write_text(
        sql, encoding="utf-8"
    )
    for ddl_name, ddl_sql in ddl_files.items():
        (project_dir / "mid" / "ddl" / ddl_name).write_text(
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


def _catalog_for_tasks_and_ddl(tmp_path, task_sql_by_name, ddl_files=None):
    project_dir = tmp_path / "demo"
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    for task_name, sql in task_sql_by_name.items():
        (project_dir / "mid" / "tasks" / task_name).write_text(
            sql,
            encoding="utf-8",
        )
    for ddl_name, ddl_sql in (ddl_files or {}).items():
        (project_dir / "mid" / "ddl").mkdir(parents=True, exist_ok=True)
        (project_dir / "mid" / "ddl" / ddl_name).write_text(
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


def test_shop_ads_store_performance_join_covers_store_snapshot_key():
    project_dir = PROJECT_ROOT / PROJECT_CONFIG["shop"]["dir"]
    catalog = build_asset_catalog(
        [],
        None,
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    sql = (
        project_dir / "ads" / "tasks" / "ads_store_performance.sql"
    ).read_text(encoding="utf-8")

    issues = task_sql_quality_defs._scan_join_before_aggregation(sql, catalog)

    assert issues == []


def test_parse_statements_filters_pure_comments():
    assert task_sql_quality_defs._parse_statements("-- only comment\n") == []
    assert task_sql_quality_defs._parse_statements("/* only comment */") == []


def test_score_code_quality_accepts_comment_only_task(tmp_path):
    context = _catalog_for_task(
        tmp_path,
        "comment_only.sql",
        "-- only comment\n",
    )

    result = score_code_quality(context)

    assert result["score"] == 100.0
    assert result["issues"] == []


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

    assert result["score"] == 60.0
    assert _issue_rule_ids(result) == {
        "CODE_TEMP_TABLE_DROPPED_IN_SAME_TASK",
        "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED",
    }
    missing_drop_issue = next(
        issue
        for issue in result["issues"]
        if issue["rule_id"] == "CODE_TEMP_TABLE_DROPPED_IN_SAME_TASK"
    )
    assert missing_drop_issue["severity"] == "中"
    assert missing_drop_issue["remediation"]["strategy"] == (
        "drop_temp_table_after_use"
    )


def test_score_code_quality_flags_pre_dropped_tmp_table_without_post_drop(
    tmp_path,
):
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

    assert "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED" in (
        _issue_rule_ids(result)
    )
    failed = [
        check
        for check in result["checks"]
        if check["rule_id"]
        == "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED"
        and not check["passed"]
    ]
    assert len(failed) == 1
    assert {
        key: failed[0][key]
        for key in (
            "rule_id",
            "target",
            "passed",
            "expected",
            "actual",
            "evidence",
            "message",
        )
    } == {
        "rule_id": "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED",
        "target": {
            "type": "table",
            "name": "tmp_sales_stage",
        },
        "passed": False,
        "expected": "DROP IF EXISTS只能清理历史残留，CREATE后需在同一作业后续DROP",
        "actual": "CREATE之后未找到后续DROP清理",
        "evidence": {
            "file": "demo/mid/tasks/dws_sales.sql",
            "table": "tmp_sales_stage",
            "reason": "pre_drop_create_without_post_drop",
            "created_statement_index": 1,
            "pre_drop_statement_indexes": [0],
            "post_create_drop_statement_indexes": [],
        },
        "message": "DROP IF EXISTS发生在CREATE之前，不能证明本次临时表生命周期闭合",
    }
    assert failed[0]["schema_version"] == "assess.diagnostic.v1"
    assert failed[0]["dimension"] == "code_quality"
    assert failed[0]["status"] == "failed"
    assert failed[0]["remediation"]["strategy"] == (
        "close_pseudo_temp_table_lifecycle"
    )


def test_score_code_quality_flags_cross_task_tmp_table_dependency(tmp_path):
    context = _catalog_for_tasks_and_ddl(
        tmp_path,
        {
            "build_tmp_sales.sql": """
DROP TABLE IF EXISTS demo.tmp_sales_stage;

CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales;
""",
            "dws_sales.sql": """
INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.tmp_sales_stage;
""",
        },
    )

    result = score_code_quality(context)

    assert "CODE_TEMP_TABLE_USED_ACROSS_TASKS" in _issue_rule_ids(result)
    failed = [
        check
        for check in result["checks"]
        if check["rule_id"] == "CODE_TEMP_TABLE_USED_ACROSS_TASKS"
        and not check["passed"]
    ]
    assert len(failed) == 1
    assert failed[0]["target"] == {
        "type": "table",
        "name": "tmp_sales_stage",
    }
    assert failed[0]["evidence"] == {
        "file": "demo/mid/tasks/build_tmp_sales.sql",
        "table": "tmp_sales_stage",
        "reason": "pre_drop_create_without_post_drop",
        "creator_task": "demo/mid/tasks/build_tmp_sales.sql",
        "reader_tasks": ["demo/mid/tasks/dws_sales.sql"],
        "created_statement_index": 1,
        "pre_drop_statement_indexes": [0],
        "post_create_drop_statement_indexes": [],
    }
    assert failed[0]["message"] == (
        "临时/过程表被其他task读取，形成跨task隐式依赖"
    )


def test_score_code_quality_flags_repeated_same_name_unclosed_lifecycle(
    tmp_path,
):
    context = _catalog_for_tasks_and_ddl(
        tmp_path,
        {
            "build_tmp_sales.sql": """
DROP TABLE IF EXISTS demo.tmp_sales_stage;

CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales;

DROP TABLE IF EXISTS demo.tmp_sales_stage;

CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales_retry;
""",
            "dws_sales.sql": """
INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.tmp_sales_stage;
""",
        },
    )

    result = score_code_quality(context)

    assert {
        "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED",
        "CODE_TEMP_TABLE_USED_ACROSS_TASKS",
    }.issubset(_issue_rule_ids(result))
    cross_task = [
        check
        for check in result["checks"]
        if check["rule_id"] == "CODE_TEMP_TABLE_USED_ACROSS_TASKS"
        and not check["passed"]
    ]
    assert len(cross_task) == 1
    assert cross_task[0]["evidence"]["created_statement_index"] == 3
    assert cross_task[0]["evidence"]["pre_drop_statement_indexes"] == [2]


def test_score_code_quality_uses_transient_facts_for_tmp_lifecycle(
    tmp_path,
    monkeypatch,
):
    context = _catalog_for_tasks_and_ddl(
        tmp_path,
        {
            "build_tmp_sales.sql": """
DROP TABLE IF EXISTS demo.tmp_sales_stage;

CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales;
""",
            "dws_sales.sql": """
INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.tmp_sales_stage;
""",
        },
    )

    monkeypatch.setattr(
        task_sql_quality_dimension,
        "_scan_task_sql",
        lambda sql: ([], [], []),
    )

    result = score_code_quality(context)

    assert {
        "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED",
        "CODE_TEMP_TABLE_USED_ACROSS_TASKS",
    }.issubset(_issue_rule_ids(result))


def test_score_code_quality_cross_task_fallback_handles_qualified_names(
    tmp_path,
    monkeypatch,
):
    context = _catalog_for_tasks_and_ddl(
        tmp_path,
        {
            "build_tmp_sales.sql": """
-- FORCE_FALLBACK
DROP TABLE IF EXISTS internal.shop_dm.tmp_sales_stage;

CREATE TABLE internal.shop_dm.tmp_sales_stage AS
SELECT order_id, amount
FROM internal.shop_dm.dwd_sales;
""",
            "dws_sales.sql": """
-- FORCE_FALLBACK
INSERT INTO internal.shop_dm.dws_sales
SELECT order_id, amount
FROM internal.shop_dm.tmp_sales_stage;
""",
        },
    )
    original_parse = task_sql_quality_defs._parse_statements

    def parse_with_forced_fallback(sql):
        if "FORCE_FALLBACK" in sql:
            return []
        return original_parse(sql)

    monkeypatch.setattr(
        task_sql_quality_defs,
        "_parse_statements",
        parse_with_forced_fallback,
    )

    result = score_code_quality(context)

    failed = [
        check
        for check in result["checks"]
        if check["rule_id"] == "CODE_TEMP_TABLE_USED_ACROSS_TASKS"
        and not check["passed"]
    ]
    assert len(failed) == 1
    assert failed[0]["evidence"]["table"] == "tmp_sales_stage"
    assert failed[0]["evidence"]["reader_tasks"] == [
        "demo/mid/tasks/dws_sales.sql"
    ]
    assert failed[0]["evidence"]["reason"] == (
        "pre_drop_create_without_post_drop"
    )


def test_score_code_quality_does_not_flag_cross_task_tmp_name_without_transient_fact(
    tmp_path,
):
    context = _catalog_for_tasks_and_ddl(
        tmp_path,
        {
            "build_tmp_sales.sql": """
CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales;
""",
            "dws_sales.sql": """
INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.tmp_sales_stage;
""",
        },
    )

    result = score_code_quality(context)

    assert "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED" not in (
        _issue_rule_ids(result)
    )
    assert "CODE_TEMP_TABLE_USED_ACROSS_TASKS" not in _issue_rule_ids(result)


def test_score_code_quality_does_not_flag_governed_tmp_named_table(
    tmp_path,
):
    context = _catalog_for_tasks_and_ddl(
        tmp_path,
        {
            "build_tmp_sales.sql": """
DROP TABLE IF EXISTS demo.tmp_sales_stage;

CREATE TABLE demo.tmp_sales_stage AS
SELECT order_id, amount
FROM demo.dwd_sales;
""",
            "dws_sales.sql": """
INSERT INTO demo.dws_sales
SELECT order_id, amount
FROM demo.tmp_sales_stage;
""",
        },
        {
            "tmp_sales_stage.sql": """
CREATE TABLE demo.tmp_sales_stage (
    order_id BIGINT,
    amount DECIMAL(18, 2)
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 1
PROPERTIES ("replication_num" = "1");
"""
        },
    )

    result = score_code_quality(context)

    assert "CODE_TEMP_TABLE_CREATED_WITH_PRE_DROP_NOT_CLEANED" not in (
        _issue_rule_ids(result)
    )
    assert "CODE_TEMP_TABLE_USED_ACROSS_TASKS" not in _issue_rule_ids(result)
    assert "CODE_TEMP_TABLE_DROPPED_IN_SAME_TASK" not in _issue_rule_ids(
        result
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
    assert len(result["checks"]) == 1
    check = result["checks"][0]
    assert {
        key: check[key]
        for key in (
            "id",
            "rule_id",
            "target",
            "passed",
            "expected",
            "actual",
            "evidence",
            "message",
        )
    } == {
        "id": "code_quality.chk_001",
        "rule_id": "CODE_NO_SELECT_STAR_IN_WRITE",
        "target": {
            "type": "task",
            "name": "demo/mid/tasks/dws_sales.sql",
        },
        "passed": False,
        "expected": "写入型语句显式列出字段",
        "actual": "写入 dws_sales 时使用 SELECT *",
        "evidence": {
            "file": "demo/mid/tasks/dws_sales.sql",
            "table": "dws_sales",
        },
        "message": "写入型语句使用SELECT *，请显式列出字段",
    }
    assert check["schema_version"] == "assess.diagnostic.v1"
    assert check["dimension"] == "code_quality"
    assert check["status"] == "failed"
    assert check["remediation"]["strategy"] == "expand_select_star"
    assert result["issues"] == [
        {
            "id": "code_quality.iss_001",
            "fingerprint": (
                "code_quality|CODE_NO_SELECT_STAR_IN_WRITE|task|"
                "demo/mid/tasks/dws_sales.sql"
            ),
            "severity": "高",
            "rule_id": "CODE_NO_SELECT_STAR_IN_WRITE",
            "target": {
                "type": "task",
                "name": "demo/mid/tasks/dws_sales.sql",
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


@pytest.mark.parametrize(
    ("task_name", "sql"),
    [
        (
            "dwd_order_customer.sql",
            """
INSERT INTO demo.dwd_order_customer
SELECT a.order_id, b.customer_name
FROM demo.dwd_order a
JOIN demo.dwd_customer b ON a.customer_id = b.customer_id;
""",
        ),
        (
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
        ),
        (
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
        ),
    ],
    ids=("keyed-join", "multiple-ctes", "explicit-cross-join"),
)
def test_score_code_quality_accepts_non_cartesian_sql(
    tmp_path, task_name, sql
):
    context = _catalog_for_task(tmp_path, task_name, sql)

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


@pytest.mark.parametrize(
    ("task_name", "sql"),
    [
        (
            "dws_customer_order_summary.sql",
            """
INSERT INTO demo.dws_customer_order_summary
SELECT customer_id, SUM(payment_amount) AS payment_amount
FROM demo.dwd_order_detail
WHERE IF(@full_refresh = 1, 1=1, order_date = CAST(@etl_date AS DATE))
GROUP BY customer_id;
""",
        ),
        (
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
        ),
        (
            "dwd_order_detail.sql",
            """
INSERT INTO demo.dwd_order_detail
SELECT order_id, pay_amount
FROM demo.ods_order
WHERE pay_time >= @etl_date
  AND pay_time < DATE_ADD(@etl_date, INTERVAL 1 DAY)
  AND store_id = 1001;
""",
        ),
    ],
    ids=("full-refresh-if", "generator-expression", "sargable-columns"),
)
def test_score_code_quality_accepts_unwrapped_filter_columns(
    tmp_path, task_name, sql
):
    context = _catalog_for_task(tmp_path, task_name, sql)

    result = score_code_quality(context)

    assert "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION" not in _issue_rule_ids(
        result
    )
