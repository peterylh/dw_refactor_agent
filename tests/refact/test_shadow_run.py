from __future__ import annotations

import json

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from refact.shadow_run import (
    _ddl_change_statements,
    _get_dml_target,
    _wait_for_table_alter_jobs,
    execute_shadow_plan,
    rewrite_sql,
    run_shadow_plan,
)


def _parse_one(sql: str):
    return sqlglot.parse_one(
        sql, dialect="doris", error_level=ErrorLevel.IGNORE
    )


def _table_refs(sql: str) -> list[tuple[str, str]]:
    statements = sqlglot.parse(
        sql, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    refs = []
    for stmt in statements:
        if stmt is None:
            continue
        for table in stmt.find_all(exp.Table):
            refs.append((table.name, table.db))
    return refs


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def test_get_dml_target_recognizes_statement_targets():
    scenarios = [
        (
            "INSERT INTO shop_dm.dwd_order_detail "
            "SELECT * FROM shop_dm.ods_order",
            "dwd_order_detail",
        ),
        ("TRUNCATE TABLE shop_dm.dwd_order_detail", "dwd_order_detail"),
        (
            "UPDATE shop_dm.dwd_order_detail "
            "SET cost_price = 0 WHERE cost_price IS NULL",
            "dwd_order_detail",
        ),
        (
            "DELETE FROM shop_dm.dws_store_sales_daily WHERE order_count = 0",
            "dws_store_sales_daily",
        ),
        (
            "CREATE TABLE shop_dm.ods_new (id BIGINT) ENGINE=OLAP "
            "DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10 "
            "PROPERTIES ('replication_num' = '1')",
            "ods_new",
        ),
    ]
    for sql, expected in scenarios:
        assert _get_dml_target(_parse_one(sql)) == expected


def test_rewrite_sql_table_mapping_scenarios():
    _assert_rewrite_sql_maps_targets_to_qa_and_keeps_ods_sources_in_prod()
    _assert_rewrite_sql_maps_recalculated_sources_to_qa()
    _assert_rewrite_sql_rewrites_recalculated_sources_inside_ctes()
    _assert_rewrite_sql_handles_multiple_dml_statements_in_one_file()


def _assert_rewrite_sql_maps_targets_to_qa_and_keeps_ods_sources_in_prod():
    sql = """
    INSERT INTO shop_dm.dwd_order_detail
    SELECT o.order_id
    FROM shop_dm.ods_order o
    JOIN shop_dm.ods_order_item i ON o.order_id = i.order_id
    """

    refs = _table_refs(rewrite_sql(sql, "shop_dm", "shop_dm_qa", set()))

    assert ("dwd_order_detail", "shop_dm_qa") in refs
    assert ("ods_order", "shop_dm") in refs
    assert ("ods_order_item", "shop_dm") in refs
    assert ("dwd_order_detail", "shop_dm") not in refs


def _assert_rewrite_sql_maps_recalculated_sources_to_qa():
    sql = """
    INSERT INTO shop_dm.ads_store_performance
    SELECT ssd.store_id, s.store_name
    FROM shop_dm.dws_store_sales_daily ssd
    LEFT JOIN shop_dm.dwd_store s ON ssd.store_id = s.store_id
    """

    refs = _table_refs(
        rewrite_sql(sql, "shop_dm", "shop_dm_qa", {"dws_store_sales_daily"})
    )

    assert ("ads_store_performance", "shop_dm_qa") in refs
    assert ("dws_store_sales_daily", "shop_dm_qa") in refs
    assert ("dwd_store", "shop_dm") in refs
    assert ("dws_store_sales_daily", "shop_dm") not in refs


def _assert_rewrite_sql_rewrites_recalculated_sources_inside_ctes():
    sql = """
    INSERT INTO shop_dm.ads_sales_dashboard
    WITH daily_base AS (
        SELECT order_date, COUNT(*) AS cnt
        FROM shop_dm.dwd_order_detail
        GROUP BY order_date
    )
    SELECT order_date, cnt FROM daily_base
    """

    refs = _table_refs(
        rewrite_sql(sql, "shop_dm", "shop_dm_qa", {"dwd_order_detail"})
    )

    assert ("ads_sales_dashboard", "shop_dm_qa") in refs
    assert ("dwd_order_detail", "shop_dm_qa") in refs
    assert ("dwd_order_detail", "shop_dm") not in refs


def _assert_rewrite_sql_handles_multiple_dml_statements_in_one_file():
    sql = """
    TRUNCATE TABLE shop_dm.dwd_order_detail;
    INSERT INTO shop_dm.dwd_order_detail
    SELECT * FROM shop_dm.ods_order;
    UPDATE shop_dm.dwd_order_detail
    SET cost_price = 0.00 WHERE cost_price IS NULL;
    """

    refs = _table_refs(rewrite_sql(sql, "shop_dm", "shop_dm_qa", set()))

    assert refs.count(("dwd_order_detail", "shop_dm_qa")) == 3
    assert ("ods_order", "shop_dm") in refs
    assert ("dwd_order_detail", "shop_dm") not in refs


def test_rewrite_sql_does_not_invent_database_prefixes():
    scenarios = [
        "SELECT * FROM some_table",
        "SET @etl_date = '2025-01-15'",
    ]
    for sql in scenarios:
        refs = _table_refs(rewrite_sql(sql, "shop_dm", "shop_dm_qa", set()))

        assert all(db not in {"shop_dm", "shop_dm_qa"} for _, db in refs)


def test_rewrite_sql_text_empty():
    assert rewrite_sql("", "shop_dm", "shop_dm_qa", set()) == ""


def test_ddl_change_statements_do_not_rewrite_invalid_multi_rename_column():
    sql = (
        "ALTER TABLE shop_dm.dwd_order_detail "
        "RENAME COLUMN unit_price price_unit, "
        "RENAME COLUMN quantity item_quantity;"
    )

    assert _ddl_change_statements(sql) == [sql]


def test_ddl_change_statements_split_semicolon_separated_statements():
    sql = (
        "ALTER TABLE shop_dm.dwd_order_detail "
        "RENAME COLUMN unit_price price_unit; "
        "ALTER TABLE shop_dm.dwd_order_detail "
        "RENAME COLUMN quantity item_quantity;"
    )

    assert _ddl_change_statements(sql) == [
        (
            "ALTER TABLE shop_dm.dwd_order_detail "
            "RENAME COLUMN unit_price price_unit;"
        ),
        (
            "ALTER TABLE shop_dm.dwd_order_detail "
            "RENAME COLUMN quantity item_quantity;"
        ),
    ]


def test_execute_shadow_plan_splits_rename_columns_and_waits(monkeypatch):
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [
            {
                "change_type": "ALTER",
                "table_name": "shop_dm.dwd_order_detail",
                "sql": (
                    "ALTER TABLE shop_dm.dwd_order_detail "
                    "RENAME COLUMN unit_price price_unit; "
                    "ALTER TABLE shop_dm.dwd_order_detail "
                    "RENAME COLUMN quantity item_quantity;"
                ),
            }
        ],
        "partition_info": {},
        "jobs_to_run": [],
        "verification": {"checks": []},
    }
    calls = []

    def fake_run_sql(sql, db="", qa=False):
        calls.append((sql, db, qa))
        return ""

    monkeypatch.setattr("refact.shadow_run.run_sql", fake_run_sql)

    execute_shadow_plan(plan)

    alter_calls = [sql for sql, _, _ in calls if sql.startswith("ALTER TABLE")]
    show_calls = [
        sql for sql, _, _ in calls if sql.startswith("SHOW ALTER TABLE COLUMN")
    ]
    assert alter_calls == [
        (
            "ALTER TABLE shop_dm_qa.dwd_order_detail "
            "RENAME COLUMN unit_price price_unit;"
        ),
        (
            "ALTER TABLE shop_dm_qa.dwd_order_detail "
            "RENAME COLUMN quantity item_quantity;"
        ),
    ]
    assert len(show_calls) == 4


def test_wait_for_table_alter_jobs_polls_until_finished(monkeypatch):
    outputs = [
        (
            "JobId\tTableName\tCreateTime\tFinishedTime\tState\tMsg\n"
            "1\tdwd_order_detail\t2026-06-30 12:00:00\tN/A\tRUNNING\t\n"
        ),
        (
            "JobId\tTableName\tCreateTime\tFinishedTime\tState\tMsg\n"
            "1\tdwd_order_detail\t2026-06-30 12:00:00\t"
            "2026-06-30 12:00:03\tFINISHED\t\n"
        ),
    ]
    calls = []

    def fake_run_sql(sql, db="", qa=False):
        calls.append((sql, db, qa))
        return outputs.pop(0)

    monkeypatch.setattr("refact.shadow_run.run_sql", fake_run_sql)
    monkeypatch.setattr("refact.shadow_run.time.sleep", lambda _: None)

    _wait_for_table_alter_jobs(
        "shop_dm_qa",
        "dwd_order_detail",
        qa=True,
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    assert len(calls) == 2
    assert calls[0][0] == (
        "SHOW ALTER TABLE COLUMN FROM `shop_dm_qa` "
        'WHERE TableName = "dwd_order_detail" '
        "ORDER BY CreateTime DESC LIMIT 10"
    )


def test_dry_run_omits_where_for_unpartitioned_checks(capsys):
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "partition_info": {},
        "jobs_to_run": [],
        "verification": {
            "checks": [
                {"table": "ads_sales_dashboard", "method": "count"},
                {
                    "table": "ads_sales_dashboard",
                    "method": "row_compare",
                },
            ]
        },
    }

    execute_shadow_plan(plan, dry_run=True)

    output = capsys.readouterr().out
    assert "WHERE * = '*'" not in output
    assert "[count] shop_dm_qa.ads_sales_dashboard" in output
    assert "[row_compare] shop_dm_qa.ads_sales_dashboard" in output


def test_run_shadow_plan_executes_self_contained(tmp_path, monkeypatch):
    job_file = tmp_path / "shop" / "tasks" / "dwd_order_detail.sql"
    job_file.parent.mkdir(parents=True)
    job_file.write_text(
        "INSERT INTO shop_dm.dwd_order_detail SELECT * FROM shop_dm.ods_order",
        encoding="utf-8",
    )
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_json(
        plan_path,
        {
            "project": "shop",
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "baseline_ddl": {},
            "ddl_changes": [],
            "partition_info": {},
            "jobs_to_run": [
                {
                    "job": "dwd_order_detail",
                    "file": "shop/tasks/dwd_order_detail.sql",
                    "layer": "DWD",
                }
            ],
            "verification": {"checks": []},
        },
    )
    calls = []

    monkeypatch.setattr("refact.shadow_run._project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "refact.shadow_run.run_sql",
        lambda sql, db="", qa=False: calls.append(("sql", sql, db, qa)),
    )
    monkeypatch.setattr(
        "refact.shadow_run.run_sql_text",
        lambda sql, db="", qa=False: calls.append(("text", sql, db, qa)),
    )

    result = run_shadow_plan(plan_path, output_path)

    assert result["status"] == "completed"
    assert result["job_count"] == 1
    assert any(call[0] == "text" for call in calls)
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
