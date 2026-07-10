DROP TABLE IF EXISTS finance_analytics_dm.ods_fraud_alerts;
-- table_id: 150e1080-785f-4e81-b239-30a742f8c5fd
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_fraud_alerts (
    -- column_id: 4c07f693-940e-430e-a309-91793ddf3e8f
    alert_id BIGINT NULL,
    -- column_id: 90283aa8-9450-4305-9fad-5650d25838a0
    transaction_id BIGINT NULL,
    -- column_id: 39c5e051-6ce6-4ca3-b03e-786af5913d6f
    customer_id BIGINT NULL,
    -- column_id: 39c19981-1aa3-4865-a61a-1fff5fea7463
    account_id BIGINT NULL,
    -- column_id: 6f12a619-4479-4b43-ba5a-ffce487c5787
    alert_date DATETIME NULL,
    -- column_id: a1db7ed0-0749-46c7-8740-367a8f2dab44
    alert_type STRING NULL,
    -- column_id: a0233031-23e9-4c7a-a3aa-1f56f7f323b7
    alert_severity STRING NULL,
    -- column_id: d4833918-c773-42fc-b9da-1e4be2f97bbf
    investigation_status STRING NULL,
    -- column_id: dd70b9e9-4f52-48c0-b0d7-ae91a4d19904
    resolution_date DATETIME NULL,
    -- column_id: f25daddf-c7ab-4f8a-9460-fd4d8207907d
    amount_recovered DECIMAL(18,4) NULL,
    -- column_id: c5073966-eed7-4f81-a757-f41c51e03df1
    assigned_to STRING NULL,
    -- column_id: 5e9c58bf-987f-4471-bacb-f3c6b78a8f56
    notes STRING NULL,
    -- column_id: f1951d35-4cc9-4af9-abd3-d1c94f8f2c33
    created_at DATETIME NULL,
    -- column_id: cb4bccd5-3803-4ff0-9881-348ad9409c4a
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(alert_id)
DISTRIBUTED BY HASH(alert_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
