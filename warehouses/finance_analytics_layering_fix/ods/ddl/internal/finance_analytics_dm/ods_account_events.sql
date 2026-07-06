DROP TABLE IF EXISTS finance_analytics_dm.ods_account_events;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_account_events (
    event_id BIGINT NULL,
    account_id BIGINT NULL,
    customer_id BIGINT NULL,
    product_id BIGINT NULL,
    event_date DATETIME NULL,
    event_type STRING NULL,
    event_category STRING NULL,
    old_value DECIMAL(18,4) NULL,
    new_value DECIMAL(18,4) NULL,
    triggered_by STRING NULL,
    channel STRING NULL,
    processed_by STRING NULL,
    notes STRING NULL,
    is_reversible BOOLEAN NULL,
    requires_approval STRING NULL,
    approval_status STRING NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(event_id)
DISTRIBUTED BY HASH(event_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
