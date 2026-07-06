DROP TABLE IF EXISTS finance_analytics_dm.dws_loan_payments;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_loan_payments (
    payment_key CHAR(32) NULL,
    account_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    scheduled_date_key CHAR(32) NULL,
    actual_date_key CHAR(32) NULL,
    payment_id BIGINT NULL,
    scheduled_date DATETIME NULL,
    actual_date DATETIME NULL,
    payment_status STRING NULL,
    payment_method STRING NULL,
    payment_completeness STRING NULL,
    delinquency_bucket STRING NULL,
    scheduled_amount DECIMAL(18,4) NULL,
    actual_amount DECIMAL(18,4) NULL,
    amount_difference DECIMAL(18,4) NULL,
    late_fee DECIMAL(18,4) NULL,
    outstanding_balance DECIMAL(18,4) NULL,
    days_late BIGINT NULL,
    late_payment_flag BOOLEAN NULL,
    missed_payment_flag BOOLEAN NULL,
    full_payment_flag BOOLEAN NULL,
    payment_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(payment_key)
DISTRIBUTED BY HASH(payment_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
