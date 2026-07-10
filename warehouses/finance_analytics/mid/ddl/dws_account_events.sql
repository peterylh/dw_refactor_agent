DROP TABLE IF EXISTS finance_analytics_dm.dws_account_events;
-- table_id: 635317dd-0f99-4e0c-bad2-f1491da05cd6
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_account_events (
    -- column_id: f9b00a2b-8370-4713-86d2-7d637c2b2924
    event_key CHAR(32) NULL,
    -- column_id: 4b52b794-9d7b-4bca-88f8-d3d58f27c0b3
    account_key CHAR(32) NULL,
    -- column_id: 6ca1ec28-4be2-4640-a78f-7d837936020a
    customer_key CHAR(32) NULL,
    -- column_id: e27c65c2-960f-4249-9c96-502e5934c710
    product_key CHAR(32) NULL,
    -- column_id: 2d7402a0-b7f8-4615-a067-ab713aac9b8c
    event_date_key CHAR(32) NULL,
    -- column_id: b5b16d5d-f0be-486f-9c82-e43f7557f83f
    event_id BIGINT NULL,
    -- column_id: 384138ac-b4f7-4e17-8ec3-af59f2f93e07
    event_date DATETIME NULL,
    -- column_id: a00f0272-a1f0-4f3a-8bfe-4be500a36b39
    event_type STRING NULL,
    -- column_id: 449295b7-ad47-4934-ace5-e459f3e44f75
    event_category STRING NULL,
    -- column_id: bf55a5e3-8f2b-443a-8bc0-3fa18c0cf8e8
    triggered_by STRING NULL,
    -- column_id: 9e3653b7-af2a-4dbe-be0a-fd9f4cf34214
    channel STRING NULL,
    -- column_id: 1bc2217b-5260-4f85-8b24-ee074e108b37
    processed_by STRING NULL,
    -- column_id: 74911436-1e2c-4a59-80c3-54026a9cb102
    approval_status STRING NULL,
    -- column_id: a978e4f9-780f-431c-9a4b-b908e6e309f9
    old_value DECIMAL(18,4) NULL,
    -- column_id: 85e52c6c-4f8a-4147-9a33-d6427248982d
    new_value DECIMAL(18,4) NULL,
    -- column_id: 9752d8fa-a03c-4008-be65-70202d627d8a
    value_change DECIMAL(18,4) NULL,
    -- column_id: cd38ff27-824b-44f7-b5b9-7465c4558de8
    reversible_flag BOOLEAN NULL,
    -- column_id: 81ffe4e8-b30e-46e7-b888-cb40a70bf2c2
    requires_approval_flag BOOLEAN NULL,
    -- column_id: fcf82ee9-8258-4536-b931-e89e763ec5e3
    approved_flag BOOLEAN NULL,
    -- column_id: dbb86699-0d8e-45e1-974e-e7d2b470667a
    pending_flag BOOLEAN NULL,
    -- column_id: c97c86d7-7b3d-4a68-8b78-518d926999a7
    rejected_flag BOOLEAN NULL,
    -- column_id: 32c17c2a-9ed5-4fc8-87f9-c5e503ce7e39
    event_type_category STRING NULL,
    -- column_id: 6fb81ffe-d5b2-4825-8629-c536010d6216
    event_count BIGINT NULL,
    -- column_id: e3486271-2dc7-411b-adb8-52b2103063f9
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(event_key)
DISTRIBUTED BY HASH(event_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
