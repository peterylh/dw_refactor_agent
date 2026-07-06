DROP TABLE IF EXISTS finance_analytics_dm.ods_loan_payments;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_loan_payments (
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
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(payment_id)
DISTRIBUTED BY HASH(payment_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
