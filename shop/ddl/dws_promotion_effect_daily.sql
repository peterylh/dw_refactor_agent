-- DWS 促销效果日汇总表
-- table_id: b3c4d5e6-f7a8-4b9c-0d1e-2f3a4b5c6d7e
DROP TABLE IF EXISTS shop_dm.dws_promotion_effect_daily;
CREATE TABLE IF NOT EXISTS shop_dm.dws_promotion_effect_daily (
    promotion_id   BIGINT        NOT NULL COMMENT '促销ID',
    stat_date      DATE          NOT NULL COMMENT '统计日期',
    promotion_name VARCHAR(128)  NULL COMMENT '促销名称',
    promotion_type VARCHAR(32)   NULL COMMENT '促销类型',
    order_count    INT           NOT NULL DEFAULT 0 COMMENT '订单数',
    customer_count INT           NOT NULL DEFAULT 0 COMMENT '客户数(去重)',
    sale_quantity  INT           NOT NULL DEFAULT 0 COMMENT '销售数量',
    sale_amount    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '销售金额',
    discount_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(promotion_id, stat_date)
PARTITION BY RANGE(stat_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(promotion_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
