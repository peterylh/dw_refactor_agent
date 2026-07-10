DROP TABLE IF EXISTS finance_analytics_dm.dim_product;
-- table_id: 65f938f0-4d3e-4601-90e9-e5726b26d766
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_product (
    -- column_id: cc437da9-8b97-450b-84d3-3ad51aaad30c
    product_key CHAR(32) NULL,
    -- column_id: 23764926-11e5-407b-9ef5-2b1601b5a47e
    product_natural_key BIGINT NULL,
    -- column_id: 418e0cb3-5538-4352-9f4d-d89916f7f3ff
    product_name STRING NULL,
    -- column_id: 0157000a-027d-4c7b-b96d-edd1dd20541f
    category STRING NULL,
    -- column_id: ed47ef20-4110-46d9-8215-a5d47868f77d
    product_line STRING NULL,
    -- column_id: 1273091e-f990-4f70-b79e-8ec07c98d7ad
    interest_rate DECIMAL(18,4) NULL,
    -- column_id: d4620aca-4463-4293-b2c6-ee5eaabffc10
    interest_rate_pct DECIMAL(18,4) NULL,
    -- column_id: f9fea213-e018-4c95-a521-f3a459ea0f34
    min_balance DECIMAL(18,4) NULL,
    -- column_id: 5f16dff9-7415-47f6-8e21-cfd84e573c47
    monthly_fee DECIMAL(18,4) NULL,
    -- column_id: 44326447-672c-406f-ae16-108a6b2e6c30
    overdraft_limit DECIMAL(18,4) NULL,
    -- column_id: f53a416b-ae3f-40aa-9534-d808612e2c74
    product_tier STRING NULL,
    -- column_id: f28157d5-61b4-4fb4-b1c9-182e7c13fdb2
    is_premium BOOLEAN NULL,
    -- column_id: 9aebc4d7-6bcf-4b38-89c7-650aa69e89ae
    product_type_desc STRING NULL,
    -- column_id: 58a0d6f8-036d-4380-9a7e-dcb80d98d8df
    fee_category STRING NULL,
    -- column_id: f24b9a33-16f6-44cd-9d72-7cdf6f8d9d24
    rate_category STRING NULL,
    -- column_id: 962672e9-9489-42a5-87b4-bab96a187a78
    complexity_score DECIMAL(18,4) NULL,
    -- column_id: 08dd926e-6dd0-41bf-9a3b-d6bd9b34f53d
    target_segment STRING NULL,
    -- column_id: a64497ed-c054-479e-9d81-79eb007774b1
    risk_level STRING NULL,
    -- column_id: c80d5da7-6adf-49f0-a0b9-69b6aa98d804
    revenue_model STRING NULL,
    -- column_id: 4d63ec3e-21e6-4363-8bca-4ac7a9323415
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(product_key)
DISTRIBUTED BY HASH(product_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
