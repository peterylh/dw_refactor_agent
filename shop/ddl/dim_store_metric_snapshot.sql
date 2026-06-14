-- DIM anti-pattern fixture: dimension table with metric group metadata
DROP TABLE IF EXISTS shop_dm.dim_store_metric_snapshot;
CREATE TABLE IF NOT EXISTS shop_dm.dim_store_metric_snapshot (
    store_id          BIGINT       NOT NULL COMMENT 'Store ID',
    snapshot_date     DATE         NOT NULL COMMENT 'Snapshot date',
    store_name        VARCHAR(128) NOT NULL COMMENT 'Store name',
    store_order_count INT          NOT NULL DEFAULT 0 COMMENT 'Store order count',
    etl_time          DATETIME     NOT NULL COMMENT 'ETL time'
) ENGINE=OLAP
UNIQUE KEY(store_id, snapshot_date)
PARTITION BY RANGE(snapshot_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(store_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
