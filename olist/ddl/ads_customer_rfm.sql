-- ADS Olist 客户RFM分析表
DROP TABLE IF EXISTS olist_dm.ads_customer_rfm;
CREATE TABLE IF NOT EXISTS olist_dm.ads_customer_rfm (
    customer_id      VARCHAR(64)   NOT NULL COMMENT '客户ID',
    stat_date        DATE          NOT NULL COMMENT '统计日期',
    recency_days     INT           NULL COMMENT '最近消费距今天数',
    frequency        INT           NULL COMMENT '消费频次(订单数)',
    monetary         DECIMAL(14,2) NULL COMMENT '消费金额',
    r_score          INT           NULL COMMENT 'R分值(1-5)',
    f_score          INT           NULL COMMENT 'F分值(1-5)',
    m_score          INT           NULL COMMENT 'M分值(1-5)',
    rfm_score        INT           NULL COMMENT 'RFM综合得分(3-15)',
    customer_segment VARCHAR(32)   NULL COMMENT '客户分层:高价值/重要发展/重要保持/一般价值/流失预警',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id, stat_date)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
