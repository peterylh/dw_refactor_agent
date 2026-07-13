DROP TABLE IF EXISTS finance_analytics_dm.ods_account_events;
-- table_id: d41ef4b5-a67d-490f-95e8-cd82817cc231
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_account_events (
    -- column_id: 452a7707-c28b-4ead-8680-b764f0e18c0a
    event_id BIGINT NULL,
    -- column_id: 2d24d57a-5938-40c9-bef3-397e3622af2c
    account_id BIGINT NULL,
    -- column_id: fa918ee7-f5a3-4c81-b940-d0ccdf6fe80e
    customer_id BIGINT NULL,
    -- column_id: 5d03f99f-fc6d-423e-b31b-853469bc53c9
    product_id BIGINT NULL,
    -- column_id: 9298500a-daf0-4d31-89d0-3f134c3d162a
    event_date DATETIME NULL,
    -- column_id: 2c83d25c-53ac-4d1f-89c1-8d58fd9e27cd
    event_type STRING NULL,
    -- column_id: 8ad3492c-e77c-4e21-a452-8ebaf4ad641b
    event_category STRING NULL,
    -- column_id: f411336b-d3be-4f76-92cd-78fce11d2e76
    old_value DECIMAL(18,4) NULL,
    -- column_id: 79bf0048-448b-4f8e-bcfa-52efafc756f0
    new_value DECIMAL(18,4) NULL,
    -- column_id: 87c4a47a-b53e-4f17-b8e7-1bbee0b9ee69
    triggered_by STRING NULL,
    -- column_id: f6309127-4a66-4722-92d9-6c40a87963b9
    channel STRING NULL,
    -- column_id: 84cf1e72-709d-45ce-b288-473904c9e1d6
    processed_by STRING NULL,
    -- column_id: 96a04780-7ef0-4670-aee5-99cfef404f05
    notes STRING NULL,
    -- column_id: d8570586-ed44-4d32-9440-abf73a57d3e1
    is_reversible BOOLEAN NULL,
    -- column_id: 0b24bc53-2b74-4aa6-b1b5-e0e9db009a1b
    requires_approval STRING NULL,
    -- column_id: c54a2b25-d8a1-40ec-ac50-bb512916ec94
    approval_status STRING NULL,
    -- column_id: 35cd38e0-fa61-4817-a3aa-f4d6da5f7d7b
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(event_id)
DISTRIBUTED BY HASH(event_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
