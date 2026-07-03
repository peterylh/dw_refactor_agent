DROP TABLE IF EXISTS finance_analytics_dm.dwd_loan_payments;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_loan_payments (
    payment_id BIGINT NULL,
    account_id BIGINT NULL,
    customer_id BIGINT NULL,
    scheduled_date DATETIME NULL,
    actual_date DATETIME NULL,
    scheduled_amount DECIMAL(18,4) NULL,
    actual_amount DECIMAL(18,4) NULL,
    is_late BOOLEAN NULL,
    days_late BIGINT NULL,
    late_fee DECIMAL(18,4) NULL,
    payment_method STRING NULL,
    outstanding_balance DECIMAL(18,4) NULL,
    payment_status STRING NULL,
    payment_completeness STRING NULL,
    amount_difference DECIMAL(18,4) NULL,
    delinquency_bucket STRING NULL,
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(payment_id)
DISTRIBUTED BY HASH(payment_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
