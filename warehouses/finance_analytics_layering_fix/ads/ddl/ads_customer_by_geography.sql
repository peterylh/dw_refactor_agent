DROP TABLE IF EXISTS finance_analytics_dm.ads_customer_by_geography;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ads_customer_by_geography (
    state VARCHAR(255) NULL,
    city STRING NULL,
    customer_count BIGINT NULL,
    pct_of_total DECIMAL(18,4) NULL,
    avg_clv STRING NULL,
    avg_income DECIMAL(18,4) NULL,
    active_count BIGINT NULL,
    last_updated DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(state)
DISTRIBUTED BY HASH(state) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
