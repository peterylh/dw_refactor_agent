DROP TABLE IF EXISTS finance_analytics_dm.ods_merchants;
-- table_id: 3dfac86e-09ec-46c6-a264-54b5335b6f04
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_merchants (
    -- column_id: 38f279e0-c36f-470f-b4a0-a60ab4edb1ce
    merchant_id BIGINT NULL,
    -- column_id: c1f1ab10-81dd-4d82-b254-0b0c54e5332a
    merchant_name STRING NULL,
    -- column_id: 3b91510a-5e2a-4cdf-a32d-4076e8014285
    category STRING NULL,
    -- column_id: 11ca5a1b-09dd-4dd8-918a-89fc88e22d9a
    mcc_code STRING NULL,
    -- column_id: 9eec2e81-8fab-4184-a24d-f693f2d4d82f
    city STRING NULL,
    -- column_id: a59a4267-7996-4f13-9db9-5f123174baaf
    state STRING NULL,
    -- column_id: 93e5733f-8bec-437f-8c39-fcd802a0fbf2
    country STRING NULL,
    -- column_id: 8b866d00-d247-4ee0-8180-0d406b9b55fe
    latitude DECIMAL(18,4) NULL,
    -- column_id: c41fc24d-d4aa-432a-876b-13df27e7318b
    longitude DECIMAL(18,4) NULL,
    -- column_id: 362dc810-b1ee-4ed9-8ed6-985581d4f40d
    risk_rating STRING NULL,
    -- column_id: 1dc951ae-acab-4d77-bf2a-827562d9c929
    avg_transaction_amount DECIMAL(18,4) NULL,
    -- column_id: a8aa2ef0-5da9-4150-995d-008d2b3968f2
    is_online BOOLEAN NULL,
    -- column_id: e02afd1a-a4d3-414e-aa9f-4501830c8d96
    established_date DATETIME NULL,
    -- column_id: a3918cea-7b1f-4a5f-83d5-9ceda509979e
    created_at DATETIME NULL,
    -- column_id: 97edd5d6-3b34-409e-bed3-32bd60a81f03
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(merchant_id)
DISTRIBUTED BY HASH(merchant_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
