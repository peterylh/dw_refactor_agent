import pytest
import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from refact.verify_run import _get_dml_target, rewrite_sql


def _parse_one(sql: str):
    return sqlglot.parse_one(sql, dialect="doris", error_level=ErrorLevel.IGNORE)


def _table_refs(sql: str) -> list[tuple[str, str]]:
    statements = sqlglot.parse(sql, dialect="doris",
                              error_level=ErrorLevel.IGNORE)
    refs = []
    for stmt in statements:
        if stmt is None:
            continue
        for table in stmt.find_all(exp.Table):
            refs.append((table.name, table.db))
    return refs


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
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
        (
            "INSERT INTO shop_dm.dwd_order_detail (order_id, customer_id) "
            "VALUES (1, 2)",
            "dwd_order_detail",
        ),
        ("SET @etl_date = '2025-01-01'", None),
    ],
)
def test_get_dml_target_recognizes_statement_targets(sql, expected):
    assert _get_dml_target(_parse_one(sql)) == expected


def test_rewrite_sql_maps_targets_to_qa_and_keeps_ods_sources_in_prod():
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


def test_rewrite_sql_maps_recalculated_sources_to_qa():
    sql = """
    INSERT INTO shop_dm.ads_store_performance
    SELECT ssd.store_id, s.store_name
    FROM shop_dm.dws_store_sales_daily ssd
    LEFT JOIN shop_dm.dwd_store s ON ssd.store_id = s.store_id
    """

    refs = _table_refs(
        rewrite_sql(sql, "shop_dm", "shop_dm_qa",
                    {"dws_store_sales_daily"})
    )

    assert ("ads_store_performance", "shop_dm_qa") in refs
    assert ("dws_store_sales_daily", "shop_dm_qa") in refs
    assert ("dwd_store", "shop_dm") in refs
    assert ("dws_store_sales_daily", "shop_dm") not in refs


def test_rewrite_sql_rewrites_recalculated_sources_inside_ctes():
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


def test_rewrite_sql_handles_multiple_dml_statements_in_one_file():
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


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM some_table",
        "SET @etl_date = '2025-01-15'",
    ],
)
def test_rewrite_sql_does_not_invent_database_prefixes(sql):
    refs = _table_refs(rewrite_sql(sql, "shop_dm", "shop_dm_qa", set()))

    assert all(db not in {"shop_dm", "shop_dm_qa"} for _, db in refs)


def test_rewrite_sql_text_empty():
    assert rewrite_sql("", "shop_dm", "shop_dm_qa", set()) == ""
