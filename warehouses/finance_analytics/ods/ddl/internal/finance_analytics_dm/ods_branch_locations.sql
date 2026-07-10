DROP TABLE IF EXISTS finance_analytics_dm.ods_branch_locations;
-- table_id: 6643dba2-836a-4c72-9ff5-5d3a48f97515
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_branch_locations (
    -- column_id: 98ddf0a6-dc98-43ac-b2f4-28d051d62341
    branch_id BIGINT NULL,
    -- column_id: 69e4454b-e2ed-4ed5-a45e-68bb535aa92e
    branch_name STRING NULL,
    -- column_id: f4e207ab-e9a3-44dc-844e-5645974ffcd5
    branch_code STRING NULL,
    -- column_id: f7137907-f0a3-4b35-a0dc-3d6509e68130
    branch_type STRING NULL,
    -- column_id: ccaa1173-194e-4900-88a2-1c8d50a047a6
    address STRING NULL,
    -- column_id: d486fb77-03a2-46f4-82ea-dc548d179030
    city STRING NULL,
    -- column_id: 1e860dc9-18e6-4115-b227-429c13dbdd7a
    state STRING NULL,
    -- column_id: a9f2b0bb-718b-438b-b2f2-d345a6b86eab
    zip_code STRING NULL,
    -- column_id: cc4bcd3e-5480-4dd6-bd77-2a1ad2b80853
    country STRING NULL,
    -- column_id: 659c0eee-1a67-453f-9205-2a2c8778140a
    latitude DECIMAL(18,4) NULL,
    -- column_id: e9faa77c-f342-4aec-94d6-78d0da041f1b
    longitude DECIMAL(18,4) NULL,
    -- column_id: 23f0202e-5e00-4e24-8115-936dbb981c70
    phone STRING NULL,
    -- column_id: e81f2302-3f98-4a35-882c-ba54e47634f1
    open_date DATETIME NULL,
    -- column_id: d5372261-bdb8-48ed-8f4c-9ee03e79562b
    is_active BOOLEAN NULL,
    -- column_id: f97c7ca3-48d1-41c0-902d-42b8097cffc9
    square_footage STRING NULL,
    -- column_id: cf7d888d-5213-423f-a416-633e42dba581
    num_employees BIGINT NULL,
    -- column_id: 810009d4-3201-469c-bab0-e74979177f65
    avg_daily_customers STRING NULL,
    -- column_id: 546a91b2-b0d6-4a76-923d-05607ffce2bc
    has_safe_deposit BOOLEAN NULL,
    -- column_id: 3d46452f-4d6f-4c2b-b3fe-adc8204ed315
    has_notary BOOLEAN NULL,
    -- column_id: e769d7de-de67-4eeb-a5c0-18e3c98b3754
    has_coin_counter BOOLEAN NULL,
    -- column_id: 04ca659c-9980-45bc-93f2-49ce9e99109a
    wheelchair_accessible STRING NULL,
    -- column_id: 6d2b5205-0949-4014-b4af-9a5c3b109d6a
    operating_hours STRING NULL,
    -- column_id: c9f2347a-7a0a-4f31-8803-a4227c30f196
    manager_name STRING NULL,
    -- column_id: 1b0d5fb7-b627-429f-bae1-deb4ab63c13a
    region STRING NULL,
    -- column_id: 1c73f5ba-f8cb-43dd-88ae-0804a9023182
    created_at DATETIME NULL,
    -- column_id: 8446a978-320b-4ea1-9dc7-4fa16a6fd484
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(branch_id)
DISTRIBUTED BY HASH(branch_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
