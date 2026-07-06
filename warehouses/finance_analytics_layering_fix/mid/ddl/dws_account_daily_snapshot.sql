DROP TABLE IF EXISTS finance_analytics_dm.dws_account_daily_snapshot;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_account_daily_snapshot (
    account_key CHAR(32) NULL,
    snapshot_date_key CHAR(32) NULL,
    customer_id BIGINT NULL,
    customer_key CHAR(32) NULL,
    product_key CHAR(32) NULL,
    snapshot_date DATETIME NULL,
    current_balance DECIMAL(18,4) NULL,
    available_balance DECIMAL(18,4) NULL,
    credit_limit DECIMAL(18,4) NULL,
    credit_utilization_pct DECIMAL(18,4) NULL,
    account_age_months BIGINT NULL,
    active_account_count BIGINT NULL,
    closed_account_count BIGINT NULL,
    dormant_account_count BIGINT NULL,
    past_due_count BIGINT NULL,
    near_limit_count BIGINT NULL,
    daily_transaction_count BIGINT NULL,
    daily_transaction_amount DECIMAL(18,4) NULL,
    daily_debit_count BIGINT NULL,
    daily_credit_count BIGINT NULL,
    account_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(account_key)
DISTRIBUTED BY HASH(account_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
