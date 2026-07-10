DROP TABLE IF EXISTS finance_analytics_dm.dwd_products;
-- table_id: cfe15dd7-9473-4ce5-9835-6dd867dd8a7f
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_products (
    -- column_id: 323a5dd6-a0f3-4322-8a0b-37525d5de581
    product_id BIGINT NULL,
    -- column_id: a51c449a-7c15-446a-889a-8a2c1d246937
    product_name STRING NULL,
    -- column_id: 54ef2ea3-64b9-482e-b641-473e8e661600
    category STRING NULL,
    -- column_id: ac91d542-2235-4b37-9f1f-48474512b4fc
    product_line STRING NULL,
    -- column_id: a43c82aa-ce82-42fd-9da1-c2c1d44bb235
    interest_rate DECIMAL(18,4) NULL,
    -- column_id: 9d31f117-dbd4-42d7-8ef0-9615a3538cd0
    interest_rate_pct DECIMAL(18,4) NULL,
    -- column_id: 541749c9-83c3-4282-9416-a4a74ae64d71
    min_balance DECIMAL(18,4) NULL,
    -- column_id: 370a76f5-71fd-4ee4-b202-30211511a4cb
    monthly_fee DECIMAL(18,4) NULL,
    -- column_id: 5d85e3ee-470d-4ff9-ba91-6029f093ebc6
    overdraft_limit DECIMAL(18,4) NULL,
    -- column_id: ed2df7fe-061f-47ad-b935-9dc2ff79a22a
    product_tier STRING NULL,
    -- column_id: 73291379-8f6f-4347-a53f-ddeb881afaf5
    is_premium BOOLEAN NULL,
    -- column_id: 72c67bc9-840c-4ea8-a0b3-4bb199fdd04c
    product_type_desc STRING NULL,
    -- column_id: 327ef2e8-ab40-4527-9fc3-28a28e2fdd6b
    fee_category STRING NULL,
    -- column_id: 38f9caef-ec85-43f7-ba9b-2b8aa6812ade
    rate_category STRING NULL,
    -- column_id: f991345e-706b-4054-be1f-af3d697e2f6c
    complexity_score DECIMAL(18,4) NULL,
    -- column_id: f68fc78b-e9e1-40a5-85e2-e640bf7a26e6
    target_segment STRING NULL,
    -- column_id: 37b63f51-fc9d-4a04-a326-9931bead43c5
    risk_level STRING NULL,
    -- column_id: 6819e912-0212-4c3c-a746-04a1d52a64e8
    revenue_model STRING NULL,
    -- column_id: 0cba98df-028d-499c-8204-652ecda4485a
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
