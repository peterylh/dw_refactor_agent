from refact.analyze_refact import (
    determine_layer,
    get_partition_col,
    parse_partition_col_from_ddl,
    strip_insert_data,
)

# ============================================================
# 1. determine_layer
# ============================================================


def test_determine_layer_ods():
    assert determine_layer("ods_order") == "ODS"
    assert determine_layer("ods_customer") == "ODS"


def test_determine_layer_dwd():
    assert determine_layer("dwd_order_detail") == "DWD"
    assert determine_layer("dwd_customer") == "DWD"


def test_determine_layer_dws():
    assert determine_layer("dws_store_sales_daily") == "DWS"
    assert determine_layer("dws_category_sales_monthly") == "DWS"


def test_determine_layer_ads():
    assert determine_layer("ads_sales_dashboard") == "ADS"
    assert determine_layer("ads_store_performance") == "ADS"


def test_determine_layer_other():
    assert determine_layer("unknown_table") == "OTHER"
    assert determine_layer("dim_date") == "OTHER"


# ============================================================
# 2. get_partition_col / parse_partition_col_from_ddl
# ============================================================


def test_get_partition_col_no_baseline():
    """没有 baseline_ddl 时返回空字符串."""
    assert get_partition_col("dwd_customer", "DWD") == ""
    assert get_partition_col("unknown_table", "ADS") == ""


def test_get_partition_col_with_baseline():
    """baseline_ddl 中有对应表时从 DDL 解析分区列."""
    ddl = """CREATE TABLE shop_dm.dwd_customer (
        snapshot_date DATE NOT NULL
    ) ENGINE=OLAP
    UNIQUE KEY(customer_id, snapshot_date)
    PARTITION BY RANGE(snapshot_date) (
        PARTITION p202501 VALUES LESS THAN ("2025-02-01")
    )
    DISTRIBUTED BY HASH(customer_id) BUCKETS 10
    PROPERTIES ("replication_num" = "1");"""
    assert get_partition_col("dwd_customer", "DWD",
                             {"dwd_customer": ddl}) == "snapshot_date"


def test_get_partition_col_with_baseline_no_partition():
    """baseline_ddl 中表无分区定义时返回空字符串."""
    ddl = """CREATE TABLE shop_dm.some_table (
        id BIGINT NOT NULL
    ) ENGINE=OLAP
    DUPLICATE KEY(id)
    DISTRIBUTED BY HASH(id) BUCKETS 10
    PROPERTIES ("replication_num" = "1");"""
    assert get_partition_col("some_table", "ADS",
                             {"some_table": ddl}) == ""


def test_get_partition_col_with_baseline_missing():
    """baseline_ddl 没有对应表时返回空字符串."""
    assert get_partition_col("ods_order", "ODS", {}) == ""
    assert get_partition_col("unknown_table", "ADS", {}) == ""


def test_parse_partition_col_from_ddl_range():
    ddl = """CREATE TABLE shop_dm.dwd_order_detail (
        order_date DATE NOT NULL
    ) ENGINE=OLAP
    UNIQUE KEY(order_date)
    PARTITION BY RANGE(order_date) (
        PARTITION p202501 VALUES LESS THAN ("2025-02-01")
    )
    DISTRIBUTED BY HASH(order_date) BUCKETS 10
    PROPERTIES ("replication_num" = "1");"""
    assert parse_partition_col_from_ddl(ddl) == "order_date"


def test_parse_partition_col_from_ddl_stat_date():
    ddl = """CREATE TABLE shop_dm.dws_store_sales_daily (
        stat_date DATE NOT NULL
    ) ENGINE=OLAP
    UNIQUE KEY(store_id, stat_date)
    PARTITION BY RANGE(stat_date) (
        PARTITION p202501 VALUES LESS THAN ("2025-02-01")
    )
    DISTRIBUTED BY HASH(store_id) BUCKETS 10
    PROPERTIES ("replication_num" = "1");"""
    assert parse_partition_col_from_ddl(ddl) == "stat_date"


def test_parse_partition_col_from_ddl_monthly():
    ddl = """CREATE TABLE shop_dm.dws_category_sales_monthly (
        stat_month_date DATE NOT NULL
    ) ENGINE=OLAP
    UNIQUE KEY(category_id, stat_month, stat_month_date)
    PARTITION BY RANGE(stat_month_date) (
        PARTITION p202501 VALUES LESS THAN ("2025-02-01")
    )
    DISTRIBUTED BY HASH(category_id) BUCKETS 10
    PROPERTIES ("replication_num" = "1");"""
    assert parse_partition_col_from_ddl(ddl) == "stat_month_date"


def test_parse_partition_col_from_ddl_no_partition():
    """表没有分区定义时返回空字符串."""
    ddl = """CREATE TABLE shop_dm.some_table (
        id BIGINT NOT NULL
    ) ENGINE=OLAP
    DUPLICATE KEY(id)
    DISTRIBUTED BY HASH(id) BUCKETS 10
    PROPERTIES ("replication_num" = "1");"""
    assert parse_partition_col_from_ddl(ddl) == ""


def test_parse_partition_col_from_ddl_empty():
    assert parse_partition_col_from_ddl("") == ""
    assert parse_partition_col_from_ddl(None) == ""


# ============================================================
# 3. strip_insert_data
# ============================================================


def test_strip_insert_data_basic():
    ddl = """DROP TABLE IF EXISTS shop_dm.ods_order;
CREATE TABLE shop_dm.ods_order (id BIGINT) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO shop_dm.ods_order VALUES (1, 'foo');
INSERT INTO shop_dm.ods_order VALUES (2, 'bar');
"""
    result = strip_insert_data(ddl)
    assert "INSERT" not in result
    assert "CREATE TABLE" in result
    assert "INSERT INTO shop_dm" not in result
    # Should keep all non-INSERT lines
    lines = result.strip().split("\n")
    assert all("INSERT" not in l.upper() for l in lines)


def test_strip_insert_data_no_insert():
    ddl = """DROP TABLE IF EXISTS shop_dm.dwd_order;
CREATE TABLE shop_dm.dwd_order (id BIGINT) ENGINE=OLAP
UNIQUE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""
    result = strip_insert_data(ddl)
    assert result.strip() == ddl.strip()
    assert "INSERT" not in result.upper()


def test_strip_insert_data_empty():
    assert strip_insert_data("") == ""
    assert strip_insert_data("  ") == "  "


def test_strip_insert_data_insert_at_start():
    ddl = """INSERT INTO shop_dm.ods_order VALUES (1);
CREATE TABLE ...;
"""
    result = strip_insert_data(ddl)
    assert result == ""


def test_strip_insert_data_multiline_insert():
    ddl = """CREATE TABLE t (id INT);

INSERT INTO shop_dm.ods_order (
    id, name
) VALUES
    (1, 'a'),
    (2, 'b');

SELECT 1;
"""
    result = strip_insert_data(ddl)
    assert "INSERT" not in result
    assert "SELECT" not in result
    assert "CREATE TABLE" in result
    # Only lines before the first INSERT remain
    assert "CREATE TABLE" in result


# ============================================================
# 4. (build_dep_graph / bfs_downstream 已迁入 tests/lineage/test_job_dag.py)
# ============================================================
