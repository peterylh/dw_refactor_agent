from collections import defaultdict, deque

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
# 2. get_partition_col
# ============================================================


def test_partition_col_dwd_dimension():
    assert get_partition_col("dwd_customer", "DWD") == "snapshot_date"
    assert get_partition_col("dwd_product", "DWD") == "snapshot_date"
    assert get_partition_col("dwd_store", "DWD") == "snapshot_date"


def test_partition_col_dwd_fact():
    assert get_partition_col("dwd_order_detail", "DWD") == "order_date"


def test_partition_col_dws_daily():
    assert get_partition_col("dws_store_sales_daily", "DWS") == "stat_date"
    assert get_partition_col("dws_product_sales_daily", "DWS") == "stat_date"
    assert get_partition_col("dws_customer_order_summary", "DWS") == "stat_date"


def test_partition_col_dws_monthly():
    assert get_partition_col("dws_category_sales_monthly", "DWS") == "stat_month_date"


def test_partition_col_ads_daily():
    assert get_partition_col("ads_sales_dashboard", "ADS") == "stat_date"
    assert get_partition_col("ads_product_topn_daily", "ADS") == "stat_date"
    assert get_partition_col("ads_customer_rfm", "ADS") == "stat_date"


def test_partition_col_ads_monthly():
    assert get_partition_col("ads_store_performance", "ADS") == "stat_month_date"


def test_partition_col_ods():
    assert get_partition_col("ods_order", "ODS") == "create_time"
    assert get_partition_col("ods_customer", "ODS") == "create_time"


def test_partition_col_fallback():
    assert get_partition_col("unknown_table", "ADS") == "stat_date"
    assert get_partition_col("some_table", "DWD") == "stat_date"


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


def test_get_partition_col_with_baseline_ddl_priority():
    """baseline_ddl 优先级高于硬编码映射."""
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


def test_get_partition_col_with_baseline_ddl_fallback():
    """baseline_ddl 没有对应表时回退到命名约定."""
    assert get_partition_col("ods_order", "ODS", {}) == "create_time"
    assert get_partition_col("unknown_table", "ADS", {}) == "stat_date"


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
# 4. build_dep_graph (inlined for test)
# ============================================================


def build_dep_graph(edges):
    deps = defaultdict(set)
    for e in edges:
        src = e["source"].rsplit(".", 1)[0]
        tgt = e["target"].rsplit(".", 1)[0]
        if src != tgt:
            deps[src].add(tgt)
    return deps


def bfs_downstream(seeds, deps):
    visited = set(seeds)
    q = deque(seeds)
    while q:
        t = q.popleft()
        for dt in deps.get(t, set()):
            if dt not in visited:
                visited.add(dt)
                q.append(dt)
    return visited - seeds


def test_build_dep_graph_empty():
    assert build_dep_graph([]) == {}


def test_build_dep_graph_basic():
    edges = [
        {"source": "ods_order.order_id", "target": "dwd_order_detail.order_id"},
        {"source": "dwd_order_detail.store_id", "target": "dws_store_sales_daily.store_id"},
        {"source": "dws_store_sales_daily.store_id", "target": "ads_store_performance.store_id"},
    ]
    deps = build_dep_graph(edges)
    assert deps["ods_order"] == {"dwd_order_detail"}
    assert deps["dwd_order_detail"] == {"dws_store_sales_daily"}
    assert deps["dws_store_sales_daily"] == {"ads_store_performance"}


def test_build_dep_graph_self_reference():
    """Self-referencing edges (same table) should be excluded."""
    edges = [
        {"source": "dwd_order_detail.order_id", "target": "dwd_order_detail.gross_profit"},
    ]
    deps = build_dep_graph(edges)
    assert deps == {}


def test_build_dep_graph_multi_target():
    edges = [
        {"source": "dwd_order_detail.store_id", "target": "dws_store_sales_daily.store_id"},
        {"source": "dwd_order_detail.product_id", "target": "dws_product_sales_daily.product_id"},
    ]
    deps = build_dep_graph(edges)
    assert deps["dwd_order_detail"] == {"dws_store_sales_daily", "dws_product_sales_daily"}


def test_bfs_downstream_empty():
    assert bfs_downstream({"t1"}, {}) == set()


def test_bfs_downstream_single_hop():
    deps = {"t1": {"t2"}}
    result = bfs_downstream({"t1"}, deps)
    assert result == {"t2"}


def test_bfs_downstream_multi_hop():
    deps = {"t1": {"t2"}, "t2": {"t3"}, "t3": {"t4"}}
    result = bfs_downstream({"t1"}, deps)
    assert result == {"t2", "t3", "t4"}


def test_bfs_downstream_branching():
    deps = {"t1": {"t2", "t3"}, "t2": {"t4"}, "t3": {"t5"}}
    result = bfs_downstream({"t1"}, deps)
    assert result == {"t2", "t3", "t4", "t5"}


def test_bfs_downstream_cycle():
    deps = {"t1": {"t2"}, "t2": {"t3"}, "t3": {"t1"}}
    result = bfs_downstream({"t1"}, deps)
    assert result == {"t2", "t3"}


def test_bfs_downstream_multiple_seeds():
    deps = {"t1": {"t2"}, "t3": {"t4"}}
    result = bfs_downstream({"t1", "t3"}, deps)
    assert result == {"t2", "t4"}


def test_bfs_downstream_no_downstream():
    deps = {"t1": {"t2"}}
    result = bfs_downstream({"t3"}, deps)
    assert result == set()
