DROP TABLE IF EXISTS finance_analytics_dm.ods_accounts;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_accounts (
    account_id BIGINT NULL,
    customer_id BIGINT NULL,
    product_id BIGINT NULL,
    account_number STRING NULL,
    account_status STRING NULL,
    open_date DATETIME NULL,
    close_date DATETIME NULL,
    current_balance DECIMAL(18,4) NULL,
    available_balance DECIMAL(18,4) NULL,
    credit_limit DECIMAL(18,4) NULL,
    currency STRING NULL,
    interest_rate DECIMAL(18,4) NULL,
    minimum_payment STRING NULL,
    payment_due_date DATETIME NULL,
    last_statement_date DATETIME NULL,
    autopay_enabled STRING NULL,
    overdraft_protection STRING NULL,
    primary_account STRING NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(account_id)
DISTRIBUTED BY HASH(account_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
