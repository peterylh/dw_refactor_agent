-- DWD anti-pattern fixture: aggregated fact in DWD
DROP TABLE IF EXISTS shop_dm.dwd_order_summary_bad;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_order_summary_bad (
    order_id     BIGINT        NOT NULL COMMENT 'Order ID',
    order_date   DATE          NOT NULL COMMENT 'Order date',
    item_count   INT           NOT NULL DEFAULT 0 COMMENT 'Item count',
    total_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT 'Total amount',
    etl_time     DATETIME      NOT NULL COMMENT 'ETL time'
) ENGINE=OLAP
UNIQUE KEY(order_id, order_date)
PARTITION BY RANGE(order_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(order_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
