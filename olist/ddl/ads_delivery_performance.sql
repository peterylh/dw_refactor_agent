-- ADS Olist 配送绩效分析表
DROP TABLE IF EXISTS olist_dm.ads_delivery_performance;
CREATE TABLE IF NOT EXISTS olist_dm.ads_delivery_performance (
    stat_date          DATE          NOT NULL COMMENT '统计日期',
    order_count        INT           NULL COMMENT '总订单数',
    on_time_count      INT           NULL COMMENT '准时送达数',
    late_count         INT           NULL COMMENT '延迟送达数',
    on_time_rate       DECIMAL(5,2)  NULL COMMENT '准时率(%)',
    avg_delivery_days  DECIMAL(6,2)  NULL COMMENT '平均配送天数',
    avg_delay_days     DECIMAL(6,2)  NULL COMMENT '平均延迟天数(仅延迟订单)',
    max_delay_days     INT           NULL COMMENT '最大延迟天数',
    etl_time           DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_date)
DISTRIBUTED BY HASH(stat_date) BUCKETS 10
PROPERTIES ("replication_num" = "1");
