-- ADS 门店绩效评估表
-- table_id: b6e00810-e675-41a8-bc53-22b826fa1e23
DROP TABLE IF EXISTS shop_dm.ads_store_performance;
CREATE TABLE IF NOT EXISTS shop_dm.ads_store_performance (
    store_id         BIGINT        NOT NULL COMMENT '门店ID',
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    stat_month_date  DATE          NOT NULL COMMENT '统计月份(月初日期)',
    store_name       VARCHAR(128)  NULL COMMENT '门店名称',
    city             VARCHAR(64)   NULL COMMENT '城市',
    store_type       VARCHAR(32)   NULL COMMENT '门店类型',
    total_orders     INT           NULL COMMENT '总订单数',
    total_amount     DECIMAL(14,2) NULL COMMENT '总销售额',
    customer_count   INT           NULL COMMENT '客户数',
    avg_order_amount DECIMAL(10,2) NULL COMMENT '客单价',
    performance_score DECIMAL(5,2) NULL COMMENT '绩效评分',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(store_id, stat_month, stat_month_date)
PARTITION BY RANGE(stat_month_date) (
    PARTITION p202406 VALUES LESS THAN ("2024-07-01")
)
DISTRIBUTED BY HASH(store_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "MONTH",
    "dynamic_partition.start" = "-24",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
