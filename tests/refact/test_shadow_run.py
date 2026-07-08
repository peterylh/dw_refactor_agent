from __future__ import annotations

import json

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from dw_refactor_agent.refactor.shadow_run import (
    ShadowRunSqlError,
    _ddl_change_statements,
    _get_dml_target,
    _wait_for_table_alter_jobs,
    execute_shadow_plan,
    main,
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


def test_rewrite_sql_qualifies_unqualified_physical_table_references():
    sql = """
    INSERT INTO dwd_order_detail
    SELECT o.order_id, d.discount_amount
    FROM ods_order o
    LEFT JOIN dwd_discount d ON o.order_id = d.order_id
    """

    rewritten = rewrite_sql(sql, "shop_dm", "shop_dm_qa", {"dwd_discount"})
    refs = _table_refs(rewritten)

    assert ("dwd_order_detail", "shop_dm_qa") in refs
    assert ("ods_order", "shop_dm") in refs
    assert ("dwd_discount", "shop_dm_qa") in refs
    assert "INSERT INTO shop_dm_qa.dwd_order_detail" in rewritten
    assert "FROM shop_dm.ods_order o" in rewritten
    assert "JOIN shop_dm_qa.dwd_discount d" in rewritten


def test_rewrite_sql_does_not_qualify_unqualified_cte_references():
    sql = """
    INSERT INTO ads_sales_dashboard
    WITH daily_base AS (
        SELECT order_date, COUNT(*) AS cnt
        FROM dwd_order_detail
        GROUP BY order_date
    )
    SELECT order_date, cnt FROM daily_base
    """

    rewritten = rewrite_sql(sql, "shop_dm", "shop_dm_qa", {"dwd_order_detail"})
    refs = _table_refs(rewritten)

    assert ("ads_sales_dashboard", "shop_dm_qa") in refs
    assert ("dwd_order_detail", "shop_dm_qa") in refs
    assert ("daily_base", "shop_dm_qa") not in refs
    assert "FROM daily_base" in rewritten


def test_rewrite_sql_does_not_invent_database_prefixes():
    scenarios = [
        "SET @etl_date = '2025-01-15'",
    ]
    for sql in scenarios:
        refs = _table_refs(rewrite_sql(sql, "shop_dm", "shop_dm_qa", set()))

        assert all(db not in {"shop_dm", "shop_dm_qa"} for _, db in refs)


def test_rewrite_sql_preserves_non_table_sql_text():
    sql = """
    SET @etl_date = COALESCE(@etl_date, CURDATE());
    -- shop_dm.dwd_customer should stay comment text
    INSERT INTO shop_dm.dwd_customer
    SELECT customer_id, CURDATE() AS snapshot_date
    FROM shop_dm.ods_customer
    WHERE created_at < CURDATE()
      AND note <> 'shop_dm.dwd_customer should stay literal'
    """

    rewritten = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())

    assert "shop_dm_qa.dwd_customer" in rewritten
    assert "shop_dm.ods_customer" in rewritten
    assert "CURDATE()" in rewritten
    assert "CURRENT_DATE" not in rewritten
    assert "-- shop_dm.dwd_customer should stay comment text" in rewritten
    assert "'shop_dm.dwd_customer should stay literal'" in rewritten


def test_rewrite_sql_maps_create_table_like_target_to_qa():
    sql = (
        "CREATE TABLE IF NOT EXISTS shop_dm.stage_store_sales_daily "
        "LIKE shop_dm.dws_store_sales_daily;"
    )

    rewritten = rewrite_sql(
        sql,
        "shop_dm",
        "shop_dm_qa",
        {"dws_store_sales_daily"},
    )

    assert "shop_dm_qa.stage_store_sales_daily" in rewritten
    assert "LIKE shop_dm_qa.dws_store_sales_daily" in rewritten


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

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql", fake_run_sql
    )

    result = execute_shadow_plan(plan)

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
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    assert phase_by_name["apply_ddl_changes"]["ddl_changes"] == [
        {
            "change_type": "ALTER",
            "sql": (
                "ALTER TABLE shop_dm_qa.dwd_order_detail "
                "RENAME COLUMN unit_price price_unit; "
                "ALTER TABLE shop_dm_qa.dwd_order_detail "
                "RENAME COLUMN quantity item_quantity;"
            ),
            "original_sql": (
                "ALTER TABLE shop_dm.dwd_order_detail "
                "RENAME COLUMN unit_price price_unit; "
                "ALTER TABLE shop_dm.dwd_order_detail "
                "RENAME COLUMN quantity item_quantity;"
            ),
            "table_name": "shop_dm_qa.dwd_order_detail",
            "status": "success",
            "error": None,
        }
    ]


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

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql", fake_run_sql
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.time.sleep", lambda _: None
    )

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


def test_dry_run_prints_anchor_tables_from_scope(capsys):
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "scope": {"anchor_tables": ["ads_store_performance"]},
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [],
        "verification": {"checks": []},
    }

    execute_shadow_plan(plan, dry_run=True)

    output = capsys.readouterr().out
    assert "锚点: ['ads_store_performance']" in output
    assert "无锚点表且无校验配置" not in output


def test_dry_run_prints_qa_ddl_changes(capsys):
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
                    "ADD COLUMN amount DECIMAL(10,2);"
                ),
            }
        ],
        "partition_info": {},
        "jobs_to_run": [],
        "verification": {"checks": []},
    }

    execute_shadow_plan(plan, dry_run=True)

    output = capsys.readouterr().out
    assert "[ALTER] shop_dm_qa.dwd_order_detail" in output
    assert (
        "ALTER TABLE shop_dm_qa.dwd_order_detail "
        "ADD COLUMN amount DECIMAL(10,2);"
    ) in output


def test_run_shadow_plan_executes_self_contained(tmp_path, monkeypatch):
    job_file = (
        tmp_path
        / "warehouses"
        / "shop"
        / "mid"
        / "tasks"
        / "dwd_order_detail.sql"
    )
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
                    "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
                    "layer": "DWD",
                }
            ],
            "verification": {"checks": []},
        },
    )
    calls = []

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: calls.append(("sql", sql, db, qa)),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql, db="", qa=False: calls.append(("text", sql, db, qa)),
    )

    result = run_shadow_plan(plan_path, output_path)

    assert result["status"] == "completed"
    assert result["mode"] == "execute"
    assert result["job_count"] == 1
    assert result["summary"]["job_count"] == 1
    assert result["summary"]["failed_job_count"] == 0
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    assert phase_by_name["run_jobs"]["jobs"] == [
        {
            "job": "dwd_order_detail",
            "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
            "layer": "DWD",
            "target": "dwd_order_detail",
            "status": "success",
            "error": None,
        }
    ]
    assert phase_by_name["compare"] == {
        "name": "compare",
        "status": "not_run",
        "checks": [],
    }
    assert any(call[0] == "text" for call in calls)
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_run_shadow_plan_persists_failed_job_result(tmp_path, monkeypatch):
    job_file = (
        tmp_path
        / "warehouses"
        / "shop"
        / "mid"
        / "tasks"
        / "dwd_order_detail.sql"
    )
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
                    "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
                    "layer": "DWD",
                }
            ],
            "verification": {
                "checks": [{"table": "ads_sales_dashboard", "method": "count"}]
            },
        },
    )

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql, db="", qa=False: (_ for _ in ()).throw(
            ShadowRunSqlError("insert failed")
        ),
    )

    result = run_shadow_plan(plan_path, output_path)

    assert result["status"] == "failed"
    assert result["mode"] == "execute"
    assert result["summary"]["failed_job_count"] == 1
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    assert phase_by_name["run_jobs"]["status"] == "failed"
    assert phase_by_name["run_jobs"]["jobs"] == [
        {
            "job": "dwd_order_detail",
            "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
            "layer": "DWD",
            "target": "dwd_order_detail",
            "status": "failed",
            "error": "insert failed",
        }
    ]
    assert phase_by_name["compare"]["status"] == "not_run"
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_execute_shadow_plan_fails_when_job_file_is_missing(
    tmp_path, monkeypatch
):
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "partition_info": {},
        "jobs_to_run": [
            {
                "job": "dwd_order_detail",
                "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
                "layer": "DWD",
            }
        ],
        "verification": {"checks": []},
    }

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda sql, db="", qa=False: "",
    )

    result = execute_shadow_plan(plan)

    assert result["status"] == "failed"
    assert result["summary"]["failed_job_count"] == 1
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    assert phase_by_name["run_jobs"]["status"] == "failed"
    job_result = phase_by_name["run_jobs"]["jobs"][0]
    assert job_result["status"] == "failed"
    assert "文件不存在" in job_result["error"]


def test_shadow_run_cli_returns_nonzero_for_failed_result(
    tmp_path, monkeypatch
):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_json(plan_path, {"project": "shop"})

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_shadow_plan",
        lambda plan, output, dry_run=False: {"status": "failed"},
    )

    assert main(["--plan", str(plan_path), "--output", str(output_path)]) == 1


def test_run_shadow_plan_dry_run_persists_phase_summary(tmp_path, monkeypatch):
    job_file = (
        tmp_path
        / "warehouses"
        / "shop"
        / "mid"
        / "tasks"
        / "M_SHOP_05_INV_DF.sql"
    )
    job_file.parent.mkdir(parents=True)
    job_file.write_text(
        (
            "SET @etl_date = COALESCE(@etl_date, CURDATE());\n"
            "INSERT INTO shop_dm.M_SHOP_05_INV_DF "
            "SELECT * FROM shop_dm.ods_inventory"
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {
            "dwd_inventory": "CREATE TABLE shop_dm.dwd_inventory (id INT)"
        },
        "ddl_changes": [
            {
                "change_type": "RENAME",
                "sql": (
                    "ALTER TABLE shop_dm.dwd_inventory "
                    "RENAME M_SHOP_05_INV_DF;"
                ),
                "old_name": "shop_dm.dwd_inventory",
                "new_name": "shop_dm.M_SHOP_05_INV_DF",
            }
        ],
        "partition_info": {"etl_date": "2025-01-15"},
        "jobs_to_run": [
            {
                "job": "M_SHOP_05_INV_DF",
                "file": "warehouses/shop/mid/tasks/M_SHOP_05_INV_DF.sql",
                "layer": "DWD",
                "target": "M_SHOP_05_INV_DF",
                "needs_etl_date": True,
            }
        ],
        "verification": {
            "checks": [
                {"table": "dws_inventory_daily", "method": "count"},
                {"table": "dws_inventory_daily", "method": "row_compare"},
            ]
        },
    }
    _write_json(plan_path, plan)

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root", lambda: tmp_path
    )

    result = run_shadow_plan(plan_path, output_path, dry_run=True)

    assert result["status"] == "dry_run"
    assert result["mode"] == "dry_run"
    assert result["summary"] == {
        "baseline_table_count": 1,
        "ddl_change_count": 1,
        "job_count": 1,
        "check_count": 2,
        "failed_job_count": 0,
        "failed_ddl_change_count": 0,
        "failed_check_count": 0,
    }
    phase_by_name = {phase["name"]: phase for phase in result["phases"]}
    assert phase_by_name["reset_qa_db"]["actions"] == [
        "DROP DATABASE IF EXISTS shop_dm_qa",
        "CREATE DATABASE shop_dm_qa",
    ]
    assert phase_by_name["create_baseline_tables"]["tables"] == [
        {"table": "dwd_inventory", "status": "dry_run"}
    ]
    assert phase_by_name["apply_ddl_changes"]["ddl_changes"] == [
        {
            "change_type": "RENAME",
            "sql": (
                "ALTER TABLE shop_dm_qa.dwd_inventory RENAME M_SHOP_05_INV_DF;"
            ),
            "original_sql": (
                "ALTER TABLE shop_dm.dwd_inventory RENAME M_SHOP_05_INV_DF;"
            ),
            "old_name": "shop_dm_qa.dwd_inventory",
            "new_name": "shop_dm_qa.M_SHOP_05_INV_DF",
            "status": "dry_run",
            "error": None,
        }
    ]
    assert phase_by_name["run_jobs"]["jobs"][0]["job"] == "M_SHOP_05_INV_DF"
    assert phase_by_name["run_jobs"]["jobs"][0]["status"] == "dry_run"
    assert phase_by_name["compare"]["status"] == "not_run"
    assert phase_by_name["compare"]["checks"] == [
        {
            "table": "dws_inventory_daily",
            "method": "count",
            "status": "not_run",
            "partition_col": None,
            "partition_value": None,
        },
        {
            "table": "dws_inventory_daily",
            "method": "row_compare",
            "status": "not_run",
            "partition_col": None,
            "partition_value": None,
        },
    ]
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_execute_shadow_plan_runs_job_once_per_execution_value(
    tmp_path, monkeypatch
):
    task_path = tmp_path / "shop" / "mid" / "tasks" / "dws_order.sql"
    task_path.parent.mkdir(parents=True)
    task_path.write_text(
        "INSERT INTO shop_dm.dws_order SELECT @etl_date;",
        encoding="utf-8",
    )
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "dws_order",
                "file": "shop/mid/tasks/dws_order.sql",
                "layer": "DWS",
                "target": "dws_order",
                "execution_values": ["2024-06-01", "2024-06-02"],
            }
        ],
        "verification": {"checks": []},
    }
    executed_texts = []

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql_text, db="", qa=False: (
            executed_texts.append(sql_text) or ""
        ),
    )

    result = execute_shadow_plan(plan)

    assert result["status"] == "completed"
    assert len(executed_texts) == 2
    assert executed_texts[0].startswith("SET @etl_date = '2024-06-01';\n")
    assert executed_texts[1].startswith("SET @etl_date = '2024-06-02';\n")


def test_execute_shadow_plan_replays_jobs_by_driver_slice(
    tmp_path, monkeypatch
):
    first_task = tmp_path / "shop" / "mid" / "tasks" / "dwd_order.sql"
    second_task = tmp_path / "shop" / "mid" / "tasks" / "dws_order.sql"
    first_task.parent.mkdir(parents=True)
    first_task.write_text(
        "INSERT INTO shop_dm.dwd_order SELECT @etl_date;",
        encoding="utf-8",
    )
    second_task.write_text(
        "INSERT INTO shop_dm.dws_order SELECT @etl_date;",
        encoding="utf-8",
    )
    plan = {
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [
            {
                "job": "dwd_order",
                "file": "shop/mid/tasks/dwd_order.sql",
                "layer": "DWD",
                "execution_values": ["2024-06-02"],
            },
            {
                "job": "dws_order",
                "file": "shop/mid/tasks/dws_order.sql",
                "layer": "DWS",
            },
        ],
        "verification": {"checks": []},
    }
    executed_texts = []

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run._project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.shadow_run.run_sql_text",
        lambda sql_text, db="", qa=False: (
            executed_texts.append(sql_text) or ""
        ),
    )

    result = execute_shadow_plan(plan)

    assert result["status"] == "completed"
    assert len(executed_texts) == 2
    assert executed_texts[0].startswith("SET @etl_date = '2024-06-02';\n")
    assert executed_texts[1].startswith("SET @etl_date = '2024-06-02';\n")
