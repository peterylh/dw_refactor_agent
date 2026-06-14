-- DWS anti-pattern fixture: detail passthrough without aggregation
DROP TABLE IF EXISTS shop_dm.dws_order_passthrough_daily;
CREATE TABLE IF NOT EXISTS shop_dm.dws_order_passthrough_daily (
    order_item_id BIGINT        NOT NULL COMMENT 'Order item ID',
    order_id      BIGINT        NOT NULL COMMENT 'Order ID',
    stat_date     DATE          NOT NULL COMMENT 'Stat date',
    store_id      BIGINT        NOT NULL COMMENT 'Store ID',
    product_id    BIGINT        NOT NULL COMMENT 'Product ID',
    subtotal      DECIMAL(12,2) NOT NULL COMMENT 'Line subtotal',
    etl_time      DATETIME      NOT NULL COMMENT 'ETL time'
) ENGINE=OLAP
UNIQUE KEY(order_item_id, stat_date)
PARTITION BY RANGE(stat_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(order_item_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
