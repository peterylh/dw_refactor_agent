DROP TABLE IF EXISTS finance_analytics_dm.dws_account_events;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_account_events (
    event_key CHAR(32) NULL,
    account_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    product_key CHAR(32) NULL,
    event_date_key CHAR(32) NULL,
    event_id BIGINT NULL,
    event_date DATETIME NULL,
    event_type STRING NULL,
    event_category STRING NULL,
    triggered_by STRING NULL,
    channel STRING NULL,
    processed_by STRING NULL,
    approval_status STRING NULL,
    old_value DECIMAL(18,4) NULL,
    new_value DECIMAL(18,4) NULL,
    value_change DECIMAL(18,4) NULL,
    reversible_flag BOOLEAN NULL,
    requires_approval_flag BOOLEAN NULL,
    approved_flag BOOLEAN NULL,
    pending_flag BOOLEAN NULL,
    rejected_flag BOOLEAN NULL,
    event_type_category STRING NULL,
    event_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(event_key)
DISTRIBUTED BY HASH(event_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
