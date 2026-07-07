DROP TABLE IF EXISTS finance_analytics_dm.ods_products;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_products (
    product_id BIGINT NULL,
    product_name STRING NULL,
    category STRING NULL,
    interest_rate DECIMAL(18,4) NULL,
    min_balance DECIMAL(18,4) NULL,
    monthly_fee DECIMAL(18,4) NULL,
    overdraft_limit DECIMAL(18,4) NULL,
    product_tier STRING NULL,
    is_premium BOOLEAN NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
