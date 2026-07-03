DROP TABLE IF EXISTS finance_analytics_dm.dws_fraud_alerts;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_fraud_alerts (
    alert_key CHAR(32) NULL,
    transaction_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    account_key CHAR(32) NULL,
    alert_date_key CHAR(32) NULL,
    resolution_date_key CHAR(32) NULL,
    alert_id BIGINT NULL,
    alert_date DATETIME NULL,
    alert_type STRING NULL,
    alert_severity STRING NULL,
    investigation_status STRING NULL,
    resolution_date DATETIME NULL,
    assigned_to STRING NULL,
    amount_recovered DECIMAL(18,4) NULL,
    resolution_days BIGINT NULL,
    resolved_flag BOOLEAN NULL,
    confirmed_fraud_flag BOOLEAN NULL,
    false_positive_flag BOOLEAN NULL,
    alert_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(alert_key)
DISTRIBUTED BY HASH(alert_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
