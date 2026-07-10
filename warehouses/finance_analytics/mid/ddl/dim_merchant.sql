DROP TABLE IF EXISTS finance_analytics_dm.dim_merchant;
-- table_id: 330df65a-5675-42b4-95a1-0fe5f7be2917
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_merchant (
    -- column_id: 36334c23-eeb2-40c6-b8f3-ccd97b436820
    merchant_key CHAR(32) NULL,
    -- column_id: 15d78fe5-ec3c-426b-8646-93bc2fb7cc5e
    merchant_natural_key BIGINT NULL,
    -- column_id: 099c1c74-921a-4b1f-b876-5f15cb524249
    merchant_name STRING NULL,
    -- column_id: ad4961d2-cbcb-40ea-91ec-923b8dbe51e3
    category STRING NULL,
    -- column_id: 031767b3-7f2d-4738-8498-db601246bfb9
    mcc_code STRING NULL,
    -- column_id: 9aebcfc6-489a-487c-bfd5-26e52c1c1e57
    category_group STRING NULL,
    -- column_id: 0c5ad4ec-3580-4818-9309-6e35d693b426
    city STRING NULL,
    -- column_id: 27004c66-40f8-4f23-b4bd-287389afecb1
    state STRING NULL,
    -- column_id: c22ab44d-1a20-4d64-89cb-57864a75de2e
    country STRING NULL,
    -- column_id: 3f59ea51-aa21-4cb4-a8cb-3e9045ea0603
    latitude DECIMAL(18,4) NULL,
    -- column_id: 4efd5b4c-2646-4b65-81ac-41c8bad71b51
    longitude DECIMAL(18,4) NULL,
    -- column_id: 43654e7a-6b4d-4956-adba-1e4cf6edc3e8
    region STRING NULL,
    -- column_id: 406c5e96-3dc7-4d25-8190-b4fa81a98867
    risk_rating STRING NULL,
    -- column_id: 1fb7ff53-9d3e-488f-a86b-e13184e478fd
    risk_score DECIMAL(18,4) NULL,
    -- column_id: e180bd19-c47c-47fa-9a3c-af83c63c53e6
    avg_transaction_amount DECIMAL(18,4) NULL,
    -- column_id: 3a0f4ab8-e396-489e-ba6d-2a78f0306bba
    transaction_value_segment STRING NULL,
    -- column_id: 03cdc596-25ab-4787-aee7-7d87d10a0fa1
    is_online BOOLEAN NULL,
    -- column_id: 2552e169-2b9a-42a5-ad37-0d2644b48b7e
    merchant_type STRING NULL,
    -- column_id: c8f83dbd-c296-42b2-94fb-7ee8c0bec70b
    established_date DATETIME NULL,
    -- column_id: 0a61c03c-da29-4a82-940d-c7620022e066
    years_in_business STRING NULL,
    -- column_id: 0085387d-58ca-42d5-9925-7f8eb7fbf1ee
    business_maturity STRING NULL,
    -- column_id: 71b58b44-ebee-4a31-ae9e-76bc825e0239
    mcc_category STRING NULL,
    -- column_id: b8d6853d-68d5-47fe-a7a5-aad31c054365
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(merchant_key)
DISTRIBUTED BY HASH(merchant_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
