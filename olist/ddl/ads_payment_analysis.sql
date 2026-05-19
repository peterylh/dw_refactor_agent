-- ADS Olist 支付方式分析表
-- table_id: 4ee56f00-48c8-4117-8147-205aee68237f
DROP TABLE IF EXISTS olist_dm.ads_payment_analysis;
CREATE TABLE IF NOT EXISTS olist_dm.ads_payment_analysis (
    stat_month          VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    payment_type        VARCHAR(32)   NOT NULL COMMENT '支付方式',
    transaction_count   INT           NULL COMMENT '交易笔数',
    total_value         DECIMAL(14,2) NULL COMMENT '总金额',
    avg_installments    DECIMAL(4,2)  NULL COMMENT '平均分期期数',
    payment_pct         DECIMAL(5,2)  NULL COMMENT '金额占比(%)',
    etl_time            DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_month, payment_type)
DISTRIBUTED BY HASH(payment_type) BUCKETS 10
PROPERTIES ("replication_num" = "1");
