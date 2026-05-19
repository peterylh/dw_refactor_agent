-- ADS 销售驾驶舱汇总表
-- table_id: cd82b3a9-ec2f-4269-8cd0-d4e8d5476a01
DROP TABLE IF EXISTS shop_dm.ads_sales_dashboard;
CREATE TABLE IF NOT EXISTS shop_dm.ads_sales_dashboard (
    stat_date          DATE          NOT NULL COMMENT '统计日期',
    total_orders       INT           NULL COMMENT '总订单数',
    total_customers    INT           NULL COMMENT '总客户数(去重)',
    total_amount       DECIMAL(14,2) NULL COMMENT '总销售额',
    total_discount     DECIMAL(14,2) NULL COMMENT '总折扣金额',
    avg_order_amount   DECIMAL(10,2) NULL COMMENT '平均客单价',
    order_growth_rate  DECIMAL(5,2)  NULL COMMENT '订单环比增长率(%)',
    amount_growth_rate DECIMAL(5,2)  NULL COMMENT '销售额环比增长率(%)',
    etl_time           DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_date)
PARTITION BY RANGE(stat_date) (
    PARTITION p202501 VALUES LESS THAN ("2025-02-01"),
    PARTITION p202502 VALUES LESS THAN ("2025-03-01"),
    PARTITION p202503 VALUES LESS THAN ("2025-04-01"),
    PARTITION p202504 VALUES LESS THAN ("2025-05-01"),
    PARTITION p202505 VALUES LESS THAN ("2025-06-01"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(stat_date) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
