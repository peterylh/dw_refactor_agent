DROP TABLE IF EXISTS finance_analytics_dm.dws_customer_monthly_summary;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_customer_monthly_summary (
    customer_key CHAR(32) NULL,
    year_month STRING NULL,
    transaction_count BIGINT NULL,
    total_transaction_volume DECIMAL(18,4) NULL,
    avg_transaction_amount DECIMAL(18,4) NULL,
    fraud_transaction_count BIGINT NULL,
    fraud_amount DECIMAL(18,4) NULL,
    unique_merchants STRING NULL,
    unique_categories STRING NULL,
    international_transaction_count BIGINT NULL,
    active_account_count BIGINT NULL,
    total_balance DECIMAL(18,4) NULL,
    avg_balance DECIMAL(18,4) NULL,
    past_due_account_count BIGINT NULL,
    fraud_rate_pct DECIMAL(18,4) NULL,
    customer_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(customer_key)
DISTRIBUTED BY HASH(customer_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
