DROP TABLE IF EXISTS finance_analytics_dm.ads_customer_by_segment;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ads_customer_by_segment (
    customer_segment VARCHAR(255) NULL,
    customer_count BIGINT NULL,
    pct_of_total DECIMAL(18,4) NULL,
    avg_clv STRING NULL,
    avg_income DECIMAL(18,4) NULL,
    avg_credit_score DECIMAL(18,4) NULL,
    avg_tenure_months STRING NULL,
    last_updated DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(customer_segment)
DISTRIBUTED BY HASH(customer_segment) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
