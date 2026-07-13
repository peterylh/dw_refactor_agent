DROP TABLE IF EXISTS finance_analytics_dm.dwd_account_events;
-- table_id: 393d4537-9a75-40bb-ad83-d3a9c20b10e4
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_account_events (
    -- column_id: fd9a058c-af06-4ab4-b257-bc4c990cc2f2
    event_id BIGINT NULL,
    -- column_id: 7248ab5a-fb9f-4498-b9bf-f94d0a6d6084
    account_id BIGINT NULL,
    -- column_id: de850305-61a2-4aad-aba9-5199c585c100
    customer_id BIGINT NULL,
    -- column_id: d4bf0269-b888-468d-85a6-9ecf1b3d9195
    product_id BIGINT NULL,
    -- column_id: 6688e440-6ce9-418e-ba07-0b07f4cd374d
    event_date DATETIME NULL,
    -- column_id: 581490b7-64a0-4302-907e-8bd89c347cf5
    event_type STRING NULL,
    -- column_id: 3db64c65-583d-477b-a5b8-597bff4bb74e
    event_category STRING NULL,
    -- column_id: 3aaa20f3-d1a9-4935-9e58-eebd53d5460d
    old_value DECIMAL(18,4) NULL,
    -- column_id: 8ee9cf71-4bf6-476b-bed7-137aa64fc38f
    new_value DECIMAL(18,4) NULL,
    -- column_id: f7f18ad4-b52b-4419-91d3-b0e9c51adb5e
    triggered_by STRING NULL,
    -- column_id: fa430b82-cea5-41b6-af89-82837e98a024
    channel STRING NULL,
    -- column_id: 5d226a9c-b1ac-4d42-afc5-f61dbc853794
    processed_by STRING NULL,
    -- column_id: df30266e-5486-41b1-ac1f-fdf5cc5f0512
    notes STRING NULL,
    -- column_id: 8362c7f4-50ab-406f-8578-04bd7592c72a
    is_reversible BOOLEAN NULL,
    -- column_id: 24fadf2a-eb91-4aea-90e8-d6ceb2f35db2
    requires_approval STRING NULL,
    -- column_id: 3891e92d-f641-4ffc-a61a-42f507936a0d
    approval_status STRING NULL,
    -- column_id: 02dd48e3-d996-4df2-9489-300d8ea73766
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(event_id)
DISTRIBUTED BY HASH(event_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
