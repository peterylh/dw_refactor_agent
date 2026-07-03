DROP TABLE IF EXISTS finance_analytics_dm.ads_product_summary;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ads_product_summary (
    total_products VARCHAR(255) NULL,
    premium_products STRING NULL,
    deposit_products STRING NULL,
    credit_products STRING NULL,
    loan_products STRING NULL,
    investment_products STRING NULL,
    avg_interest_rate_pct DECIMAL(18,4) NULL,
    avg_monthly_fee DECIMAL(18,4) NULL,
    last_updated DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(total_products)
DISTRIBUTED BY HASH(total_products) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
