import json

from dw_refactor_agent.refactor.compare import (
    check_row_compare,
    compare_shadow_results,
    fmt_val,
    run_checks,
)
from dw_refactor_agent.refactor.plan_artifact import write_verification_plan


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursors):
        self.cursors = list(cursors)
        self.closed = False

    def cursor(self):
        return self.cursors.pop(0)

    def close(self):
        self.closed = True


def test_fmt_val_formats_supported_scalar_values():
    scenarios = [
        (None, "NULL"),
        (123, "123"),
        (3.14159, "3.141590"),
        ("hello", "hello"),
    ]

    for value, expected in scenarios:
        assert fmt_val(value) == expected


def test_run_checks_compares_count_self_contained(monkeypatch):
    prod_conn = FakeConn([FakeCursor([(12,)])])
    qa_conn = FakeConn([FakeCursor([(12,)])])

    def fake_conn(db_name, qa=False):
        return qa_conn if qa else prod_conn

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn", fake_conn
    )

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "verification": {
                "checks": [{"table": "ads_sales_dashboard", "method": "count"}]
            },
        },
        method="count",
    )

    assert result["all_pass"] is True
    assert result["results"][0]["prod_count"] == 12
    assert result["results"][0]["qa_count"] == 12
    assert prod_conn.closed is True
    assert qa_conn.closed is True


def test_run_checks_uses_compare_anchor_for_partition_filter(monkeypatch):
    prod_cursor = FakeCursor([(3,)])
    qa_cursor = FakeCursor([(3,)])
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    def fake_conn(db_name, qa=False):
        return qa_conn if qa else prod_conn

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn", fake_conn
    )

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "verification": {
                "compare_anchors": {
                    "ads_store_performance": {
                        "time_column": "stat_month_date",
                        "time_period": "M",
                        "anchor_time_value": "2024-06-01",
                    }
                },
                "checks": [
                    {"table": "ads_store_performance", "method": "count"}
                ],
            },
        },
        method="count",
    )

    assert result["all_pass"] is True
    assert prod_cursor.executed == [
        "SELECT COUNT(*) FROM ads_store_performance "
        "WHERE stat_month_date = '2024-06-01'"
    ]
    assert qa_cursor.executed == prod_cursor.executed


def test_row_compare_excludes_configured_columns_case_insensitively():
    prod_cursor = FakeCursor(
        [
            [("order_id",), ("amount",), ("etl_time",)],
            [(1, 10, "2026-07-04 10:00:00")],
        ]
    )
    qa_cursor = FakeCursor(
        [
            [(1, 10, "2026-07-04 10:05:00")],
        ]
    )
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    result = check_row_compare(
        prod_conn,
        qa_conn,
        {
            "table": "dws_order",
            "method": "row_compare",
            "exclude_columns": ["ETL_TIME"],
        },
        sample=0,
        precision=0.01,
    )

    assert result["match"] is True
    assert result["compared_columns"] == ["order_id", "amount"]
    assert result["ignored_columns"] == ["etl_time"]
    assert prod_cursor.executed == [
        "DESC dws_order",
        "SELECT order_id, amount FROM dws_order ORDER BY order_id, amount ",
    ]
    assert qa_cursor.executed == [
        "SELECT order_id, amount FROM dws_order ORDER BY order_id, amount ",
    ]


def test_row_compare_defaults_to_ignore_etl_time_for_legacy_checks():
    prod_cursor = FakeCursor(
        [
            [("order_id",), ("amount",), ("etl_time",)],
            [(1, 10, "2026-07-04 10:00:00")],
        ]
    )
    qa_cursor = FakeCursor(
        [
            [(1, 10, "2026-07-04 10:05:00")],
        ]
    )
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    result = check_row_compare(
        prod_conn,
        qa_conn,
        {"table": "dws_order", "method": "row_compare"},
        sample=0,
        precision=0.01,
    )

    assert result["match"] is True
    assert result["compared_columns"] == ["order_id", "amount"]
    assert result["ignored_columns"] == ["etl_time"]


def test_row_compare_empty_exclude_columns_compares_all_columns():
    prod_cursor = FakeCursor(
        [
            [("order_id",), ("amount",), ("etl_time",)],
            [(1, 10, "2026-07-04 10:00:00")],
        ]
    )
    qa_cursor = FakeCursor(
        [
            [(1, 10, "2026-07-04 10:05:00")],
        ]
    )
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    result = check_row_compare(
        prod_conn,
        qa_conn,
        {
            "table": "dws_order",
            "method": "row_compare",
            "exclude_columns": [],
        },
        sample=0,
        precision=0.01,
    )

    assert result["match"] is False
    assert result["compared_columns"] == ["order_id", "amount", "etl_time"]
    assert result["ignored_columns"] == []
    assert result["detail"] == [
        {
            "row": 0,
            "diffs": [
                {
                    "col": "etl_time",
                    "prod": "2026-07-04 10:00:00",
                    "qa": "2026-07-04 10:05:00",
                }
            ],
        }
    ]


def test_row_compare_missing_columns_returns_failed_result():
    result = check_row_compare(
        FakeConn([FakeCursor([[]])]),
        FakeConn([FakeCursor([])]),
        {"table": "empty_table", "method": "row_compare"},
        sample=0,
        precision=0.01,
    )

    assert result["match"] is False
    assert result["error"] == "无列信息"


def test_run_checks_short_circuit_scenarios(monkeypatch):
    def fail_if_called(db_name, qa=False):
        raise AssertionError("short-circuit plans should not open connections")

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn", fail_if_called
    )

    scenarios = [
        (
            "legacy_top_level_checks",
            {
                "project_db": "shop_dm",
                "qa_db": "shop_dm_qa",
                "checks": [
                    {"table": "ads_sales_dashboard", "method": "count"}
                ],
            },
            {"all_pass": True, "results": []},
        ),
        (
            "no_data_anchor",
            {
                "project_db": "shop_dm",
                "qa_db": "shop_dm_qa",
                "affected_scope": {"direct_tables": ["dws_terminal"]},
                "jobs_to_run": [
                    {
                        "job": "dws_terminal",
                        "target": "dws_terminal",
                    }
                ],
                "verification": {
                    "checks": [],
                    "data_anchor_status": "none",
                    "data_anchor_reason": (
                        "no invariant downstream anchor tables"
                    ),
                },
            },
            {
                "all_pass": False,
                "status": "no_data_anchor",
                "reason": "no invariant downstream anchor tables",
                "results": [],
            },
        ),
        (
            "schema_anchor_blocked",
            {
                "project_db": "shop_dm",
                "qa_db": "shop_dm_qa",
                "verification": {
                    "schema_anchor_status": "blocked",
                    "schema_anchor_reason": (
                        "ADS table definitions must remain unchanged"
                    ),
                    "checks": [{"table": "ads_final", "method": "count"}],
                },
            },
            {
                "all_pass": False,
                "status": "schema_anchor_blocked",
                "reason": "ADS table definitions must remain unchanged",
                "results": [],
            },
        ),
    ]

    for scenario_name, plan, expected in scenarios:
        assert run_checks(plan, method="count") == expected, scenario_name


def test_compare_shadow_results_writes_compare_output(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    write_verification_plan(
        plan_path,
        {
            "project": "shop",
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "baseline_ddl": {},
        },
    )

    def fake_run_checks(meta, method="all", sample=0, precision=0.01):
        assert meta["baseline_ddl"] == {}
        return {
            "all_pass": True,
            "results": [],
            "method": method,
            "sample": sample,
            "precision": precision,
        }

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.run_checks", fake_run_checks
    )

    result = compare_shadow_results(
        plan_path,
        output_path,
        method="count",
        sample=10,
        precision=0.1,
    )

    assert result["method"] == "count"
    assert result["sample"] == 10
    assert result["precision"] == 0.1
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
