DROP TABLE IF EXISTS finance_analytics_dm.ods_fraud_alerts;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_fraud_alerts (
    alert_id BIGINT NULL,
    transaction_id BIGINT NULL,
    customer_id BIGINT NULL,
    account_id BIGINT NULL,
    alert_date DATETIME NULL,
    alert_type STRING NULL,
    alert_severity STRING NULL,
    investigation_status STRING NULL,
    resolution_date DATETIME NULL,
    amount_recovered DECIMAL(18,4) NULL,
    assigned_to STRING NULL,
    notes STRING NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(alert_id)
DISTRIBUTED BY HASH(alert_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
