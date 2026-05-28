-- ADS 促销投资回报分析表
-- table_id: d5e6f7a8-b9c0-4d1e-2f3a-4b5c6d7e8f9a
DROP TABLE IF EXISTS shop_dm.ads_promotion_roi;
CREATE TABLE IF NOT EXISTS shop_dm.ads_promotion_roi (
    promotion_id      BIGINT        NOT NULL COMMENT '促销ID',
    stat_date         DATE          NOT NULL COMMENT '统计日期',
    promotion_name    VARCHAR(128)  NULL COMMENT '促销名称',
    promotion_type    VARCHAR(32)   NULL COMMENT '促销类型',
    total_orders      INT           NOT NULL DEFAULT 0 COMMENT '总订单数',
    total_sale_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总销售金额',
    total_discount_cost DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总折扣成本',
    avg_discount_rate DECIMAL(5,2)  NULL COMMENT '平均折扣率',
    roi               DECIMAL(10,2) NULL COMMENT '投资回报率:销售额/折扣成本',
    etl_time          DATETIME      NOT NULL COMMENT 'ETL处理时间'
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
