-- DWS 库存日汇总表
-- table_id: c4d5e6f7-a8b9-4c0d-1e2f-3a4b5c6d7e8f
DROP TABLE IF EXISTS shop_dm.dws_inventory_daily;
CREATE TABLE IF NOT EXISTS shop_dm.dws_inventory_daily (
    product_id        BIGINT      NOT NULL COMMENT '商品ID',
    store_id          BIGINT      NOT NULL COMMENT '门店ID',
    stat_date         DATE        NOT NULL COMMENT '统计日期',
    quantity          INT         NOT NULL DEFAULT 0 COMMENT '库存数量',
    safety_stock      INT         NOT NULL DEFAULT 10 COMMENT '安全库存',
    stock_status      VARCHAR(16) NULL COMMENT '库存状态:正常/偏低/缺货预警/缺货',
    days_since_restock INT        NULL COMMENT '距上次补货天数',
    etl_time          DATETIME    NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(product_id, store_id, stat_date)
PARTITION BY RANGE(stat_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(product_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
