-- ADS 库存预警分析表
-- table_id: e6f7a8b9-c0d1-4e2f-3a4b-5c6d7e8f9a0b
DROP TABLE IF EXISTS shop_dm.ads_inventory_alert;
CREATE TABLE IF NOT EXISTS shop_dm.ads_inventory_alert (
    product_id          BIGINT        NOT NULL COMMENT '商品ID',
    store_id            BIGINT        NOT NULL COMMENT '门店ID',
    stat_date           DATE          NOT NULL COMMENT '统计日期',
    product_name        VARCHAR(128)  NULL COMMENT '商品名称',
    store_name          VARCHAR(128)  NULL COMMENT '门店名称',
    quantity            INT           NOT NULL DEFAULT 0 COMMENT '库存数量',
    safety_stock        INT           NOT NULL DEFAULT 10 COMMENT '安全库存',
    stock_status        VARCHAR(16)   NULL COMMENT '库存状态:正常/偏低/缺货预警/缺货',
    days_since_restock  INT           NULL COMMENT '距上次补货天数',
    daily_sales_velocity DECIMAL(10,2) NULL COMMENT '日均销售数量(近7天)',
    days_of_stock_remaining DECIMAL(5,1) NULL COMMENT '预计库存可支撑天数',
    alert_level         VARCHAR(16)   NULL COMMENT '预警级别:正常/关注/预警/严重',
    etl_time            DATETIME      NOT NULL COMMENT 'ETL处理时间'
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
