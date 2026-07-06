DROP TABLE IF EXISTS finance_analytics_dm.dwd_products;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_products (
    product_id BIGINT NULL,
    product_name STRING NULL,
    category STRING NULL,
    product_line STRING NULL,
    interest_rate DECIMAL(18,4) NULL,
    interest_rate_pct DECIMAL(18,4) NULL,
    min_balance DECIMAL(18,4) NULL,
    monthly_fee DECIMAL(18,4) NULL,
    overdraft_limit DECIMAL(18,4) NULL,
    product_tier STRING NULL,
    is_premium BOOLEAN NULL,
    product_type_desc STRING NULL,
    fee_category STRING NULL,
    rate_category STRING NULL,
    complexity_score DECIMAL(18,4) NULL,
    target_segment STRING NULL,
    risk_level STRING NULL,
    revenue_model STRING NULL,
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
