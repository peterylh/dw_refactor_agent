import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from refact.verify_run import _get_dml_target, rewrite_sql

# ============================================================
# 1. _get_dml_target
# ============================================================


def _parse_one(sql: str):
    return sqlglot.parse_one(sql, dialect="doris", error_level=ErrorLevel.IGNORE)


def test_get_dml_target_insert():
    stmt = _parse_one("INSERT INTO shop_dm.dwd_order_detail SELECT * FROM shop_dm.ods_order")
    assert _get_dml_target(stmt) == "dwd_order_detail"


def test_get_dml_target_truncate():
    stmt = _parse_one("TRUNCATE TABLE shop_dm.dwd_order_detail")
    assert _get_dml_target(stmt) == "dwd_order_detail"


def test_get_dml_target_update():
    stmt = _parse_one("UPDATE shop_dm.dwd_order_detail SET cost_price = 0 WHERE cost_price IS NULL")
    assert _get_dml_target(stmt) == "dwd_order_detail"


def test_get_dml_target_delete():
    stmt = _parse_one("DELETE FROM shop_dm.dws_store_sales_daily WHERE order_count = 0")
    assert _get_dml_target(stmt) == "dws_store_sales_daily"


def test_get_dml_target_create():
    stmt = _parse_one("CREATE TABLE shop_dm.ods_new (id BIGINT) ENGINE=OLAP DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10 PROPERTIES ('replication_num' = '1')")
    assert _get_dml_target(stmt) == "ods_new"


def test_get_dml_target_set():
    """SET statement has no DML target."""
    stmt = _parse_one("SET @etl_date = '2025-01-01'")
    assert _get_dml_target(stmt) is None


def test_get_dml_target_insert_columns():
    """INSERT INTO t(a,b) should still recognize t as target."""
    stmt = _parse_one("INSERT INTO shop_dm.dwd_order_detail (order_id, customer_id) VALUES (1, 2)")
    assert _get_dml_target(stmt) == "dwd_order_detail"


# ============================================================
# 2. rewrite_sql
# ============================================================


def test_rewrite_insert_target_to_qa():
    sql = "INSERT INTO shop_dm.dwd_order_detail SELECT * FROM shop_dm.ods_order WHERE shop_dm.ods_order.status = '已完成'"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm_qa.dwd_order_detail" in result
    assert "shop_dm.ods_order" in result
    assert "shop_dm_qa" not in result.replace("shop_dm_qa.dwd_order_detail", "")


def test_rewrite_truncate_target_to_qa():
    sql = "TRUNCATE TABLE shop_dm.dwd_order_detail"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm_qa.dwd_order_detail" in result
    # TRUNCATE only has target, so no FROM references
    assert "shop_dm.dwd_order_detail" not in result


def test_rewrite_update_target_to_qa():
    sql = "UPDATE shop_dm.dwd_order_detail SET cost_price = ROUND(unit_price * 0.60, 2) WHERE cost_price IS NULL"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm_qa.dwd_order_detail" in result
    assert "shop_dm.dwd_order_detail" not in result


def test_rewrite_delete_target_to_qa():
    sql = "DELETE FROM shop_dm.dws_store_sales_daily WHERE order_count = 0"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm_qa.dws_store_sales_daily" in result
    assert "shop_dm.dws_store_sales_daily" not in result


def test_rewrite_recalculated_source_to_qa():
    """When source table is in recalculated set, it should be rewritten to QA."""
    sql = "INSERT INTO shop_dm.dws_store_sales_daily SELECT store_id, order_date FROM shop_dm.dwd_order_detail"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", {"dwd_order_detail"})
    # Target → QA
    assert "shop_dm_qa.dws_store_sales_daily" in result
    # Recalculated source → QA
    assert "shop_dm_qa.dwd_order_detail" in result
    assert "shop_dm.dwd_order_detail" not in result


def test_rewrite_ods_source_stays_prod():
    """ODS source without recalculated flag should stay in production."""
    sql = "INSERT INTO shop_dm.dwd_order_detail SELECT * FROM shop_dm.ods_order JOIN shop_dm.ods_order_item"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm_qa.dwd_order_detail" in result  # target
    assert "shop_dm.ods_order" in result  # ODS → prod
    assert "shop_dm.ods_order_item" in result  # ODS → prod


def test_rewrite_mixed_sources():
    """Some sources recalculated, some not."""
    sql = ("INSERT INTO shop_dm.ads_store_performance "
           "SELECT ssd.store_id, s.store_name "
           "FROM shop_dm.dws_store_sales_daily ssd "
           "LEFT JOIN shop_dm.dwd_store s ON ssd.store_id = s.store_id")
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", {"dws_store_sales_daily"})
    assert "shop_dm_qa.ads_store_performance" in result  # target
    assert "shop_dm_qa.dws_store_sales_daily" in result  # recalculated → QA
    assert "shop_dm.dwd_store" in result  # not recalculated → prod


def test_rewrite_cte():
    """CTE source tables should be rewritten when in recalculated set."""
    sql = """INSERT INTO shop_dm.ads_sales_dashboard
WITH daily_base AS (
    SELECT order_date, COUNT(*) AS cnt
    FROM shop_dm.dwd_order_detail
    GROUP BY order_date
)
SELECT stat_date, cnt FROM daily_base"""
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", {"dwd_order_detail"})
    assert "shop_dm_qa.ads_sales_dashboard" in result  # target
    assert "shop_dm_qa.dwd_order_detail" in result  # recalculated in CTE


def test_rewrite_multiple_statements():
    """Multiple statements in one file should all be rewritten."""
    sql = """TRUNCATE TABLE shop_dm.dwd_order_detail;
INSERT INTO shop_dm.dwd_order_detail
SELECT * FROM shop_dm.ods_order;
UPDATE shop_dm.dwd_order_detail SET cost_price = 0.00 WHERE cost_price IS NULL;"""
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    # TRUNCATE target → QA
    assert "shop_dm_qa.dwd_order_detail" in result
    assert result.count("shop_dm_qa.dwd_order_detail") == 3  # TRUNCATE + INSERT + UPDATE
    # source → prod
    assert "shop_dm.ods_order" in result
    # No un-rewritten target refs
    for phrase in ["TRUNCATE TABLE shop_dm.dwd_order_detail",
                   "INSERT INTO shop_dm.dwd_order_detail",
                   "UPDATE shop_dm.dwd_order_detail"]:
        assert phrase not in result, f"Found unrewritten: {phrase}"


def test_rewrite_self_join_update():
    """UPDATE with self-reference: target always → QA."""
    sql = "UPDATE shop_dm.dwd_order_detail SET gross_profit = ROUND(subtotal - cost_price * quantity, 2)"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm_qa.dwd_order_detail" in result


def test_rewrite_no_db_prefix():
    """Table without db prefix should not be modified."""
    sql = "SELECT * FROM some_table"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm." not in result
    assert "shop_dm_qa." not in result


def test_rewrite_sql_text_empty():
    assert rewrite_sql("", "shop_dm", "shop_dm_qa", set()) == ""


def test_rewrite_sql_text_set_variable():
    """SET variable shouldn't trigger rewriting."""
    sql = "SET @etl_date = '2025-01-15'"
    result = rewrite_sql(sql, "shop_dm", "shop_dm_qa", set())
    assert "shop_dm" not in result
