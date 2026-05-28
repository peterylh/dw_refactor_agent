-- DWD 库存快照宽表
-- table_id: a2b3c4d5-e6f7-4a8b-9c0d-1e2f3a4b5c6d
DROP TABLE IF EXISTS shop_dm.dwd_inventory;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_inventory (
    inventory_id      BIGINT   NOT NULL COMMENT '库存记录ID',
    snapshot_date     DATE     NOT NULL COMMENT '快照日期',
    etl_time          DATETIME NOT NULL COMMENT 'ETL处理时间',
    product_id        BIGINT   NOT NULL COMMENT '商品ID',
    store_id          BIGINT   NOT NULL COMMENT '门店ID',
    quantity          INT      NOT NULL COMMENT '库存数量',
    safety_stock      INT      NOT NULL DEFAULT 10 COMMENT '安全库存',
    stock_status      VARCHAR(16) NULL COMMENT '库存状态:正常/偏低/缺货预警/缺货',
    last_restock_date DATE     NULL COMMENT '最近补货日期',
    days_since_restock INT     NULL COMMENT '距上次补货天数'
) ENGINE=OLAP
UNIQUE KEY(inventory_id, snapshot_date)
PARTITION BY RANGE(snapshot_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(inventory_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
