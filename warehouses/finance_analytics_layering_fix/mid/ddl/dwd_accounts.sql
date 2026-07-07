DROP TABLE IF EXISTS finance_analytics_dm.dwd_accounts;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_accounts (
    account_id BIGINT NULL,
    customer_id BIGINT NULL,
    product_id BIGINT NULL,
    account_number STRING NULL,
    account_status STRING NULL,
    open_date DATETIME NULL,
    close_date DATETIME NULL,
    account_age_months BIGINT NULL,
    is_active BOOLEAN NULL,
    is_closed BOOLEAN NULL,
    is_dormant BOOLEAN NULL,
    current_balance DECIMAL(18,4) NULL,
    available_balance DECIMAL(18,4) NULL,
    credit_limit DECIMAL(18,4) NULL,
    credit_utilization_pct DECIMAL(18,4) NULL,
    balance_category STRING NULL,
    currency STRING NULL,
    interest_rate DECIMAL(18,4) NULL,
    minimum_payment STRING NULL,
    payment_due_date DATETIME NULL,
    last_statement_date DATETIME NULL,
    autopay_enabled STRING NULL,
    overdraft_protection STRING NULL,
    primary_account STRING NULL,
    is_past_due BOOLEAN NULL,
    is_near_limit BOOLEAN NULL,
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(account_id)
DISTRIBUTED BY HASH(account_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
