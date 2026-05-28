-- ADS 客户RFM分析表
-- table_id: b79f7d88-bbb7-4fbc-b61e-96f6c3aafd11
DROP TABLE IF EXISTS shop_dm.ads_customer_rfm;
CREATE TABLE IF NOT EXISTS shop_dm.ads_customer_rfm (
    customer_id      BIGINT        NOT NULL COMMENT '客户ID',
    stat_date        DATE          NOT NULL COMMENT '统计日期',
    recency_days     INT           NULL COMMENT '最近一次消费距今天数',
    frequency        INT           NULL COMMENT '消费频次',
    monetary         DECIMAL(14,2) NULL COMMENT '消费金额',
    r_score          INT           NULL COMMENT 'R分值(1-5)',
    f_score          INT           NULL COMMENT 'F分值(1-5)',
    m_score          INT           NULL COMMENT 'M分值(1-5)',
    rfm_score        INT           NULL COMMENT 'RFM综合得分(3-15)',
    customer_segment VARCHAR(32)   NULL COMMENT '客户分层:高价值/重要发展/重要保持/一般价值/流失预警',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id, stat_date)
PARTITION BY RANGE(stat_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
