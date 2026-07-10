DROP TABLE IF EXISTS finance_analytics_dm.ods_atm_locations;
-- table_id: e9958108-1a2c-4b23-8bc2-20386068c2be
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_atm_locations (
    -- column_id: a5d21787-989d-4b19-b07a-b9607fb788e1
    atm_id BIGINT NULL,
    -- column_id: 5cbbbd16-9d3d-482b-87ba-e2ccfde8368a
    atm_code STRING NULL,
    -- column_id: d46507eb-1af7-4bcf-86f9-1263437118d8
    location_name STRING NULL,
    -- column_id: 4f11228a-3c37-4211-a771-8811fe665721
    location_type STRING NULL,
    -- column_id: 6366f9f1-43ad-47ab-9fe4-467c020ef25f
    address STRING NULL,
    -- column_id: 6ea67c82-559b-429d-996b-2b3a0afbd693
    city STRING NULL,
    -- column_id: 6f18a47c-9d82-4968-a75e-6f9a137c5f2a
    state STRING NULL,
    -- column_id: eaa78781-e463-4de4-b9d9-8848be120e3b
    zip_code STRING NULL,
    -- column_id: 5b590458-99c4-43b2-ba24-2969edf34a30
    country STRING NULL,
    -- column_id: 74c9281f-d1d9-42c1-b6f2-b628c2ef19dc
    latitude DECIMAL(18,4) NULL,
    -- column_id: a40548f1-675c-4e79-8878-1df80592191b
    longitude DECIMAL(18,4) NULL,
    -- column_id: 89bef141-eb07-42ba-8b12-656e8db42e5b
    install_date DATETIME NULL,
    -- column_id: 9931cd74-790e-4b26-9b4f-ff93c95f36c5
    is_operational BOOLEAN NULL,
    -- column_id: d9b03094-a5cb-4a3f-bd85-26a5d38e6dd6
    is_deposit_enabled BOOLEAN NULL,
    -- column_id: 510c802c-05fa-487c-a549-93bef2622c54
    is_cash_only BOOLEAN NULL,
    -- column_id: 2c447e0b-b250-478b-86a6-db157835740d
    max_withdrawal_amount DECIMAL(18,4) NULL,
    -- column_id: 3af7674d-6acd-4f61-9de6-074cdf79de9e
    daily_transaction_limit BIGINT NULL,
    -- column_id: 2d18b410-262b-4a44-b40f-86b0ad6aca0c
    avg_daily_transactions BIGINT NULL,
    -- column_id: 3e9fce5a-8539-455b-ab17-aa5f4f2d7031
    cash_capacity STRING NULL,
    -- column_id: 5c26704c-fbe5-4264-a101-67a5c34ea3a5
    last_refill_date DATETIME NULL,
    -- column_id: d3408a7c-97ec-410c-a9d4-328d2d527dfa
    last_maintenance_date DATETIME NULL,
    -- column_id: 7da6fe8e-2c82-4255-93d3-adf639ac6faa
    surcharge_fee DECIMAL(18,4) NULL,
    -- column_id: cbe8f18b-d903-404a-b2dc-fae21c478f9a
    is_24_hour BOOLEAN NULL,
    -- column_id: 8218ec16-818d-4026-ac46-244f80a015aa
    has_camera BOOLEAN NULL,
    -- column_id: 21e7d163-4ef1-4dad-b5ea-4fb52fcb5485
    branch_id BIGINT NULL,
    -- column_id: db746d82-dd91-4de9-a6e4-85b84677844e
    created_at DATETIME NULL,
    -- column_id: 7f942bd0-c735-4a3e-a8c9-03ecdc04025c
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(atm_id)
DISTRIBUTED BY HASH(atm_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
