DROP TABLE IF EXISTS finance_analytics_dm.dws_customer_monthly_summary;
-- table_id: 5b64cba4-b950-4a3a-9f14-38ac794214e2
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_customer_monthly_summary (
    -- column_id: 6b62fd18-2203-4cbb-b78d-727e1782af79
    customer_key CHAR(32) NULL,
    -- column_id: f9382af7-d7e2-4e8f-a51b-f223b5a8e2a5
    year_month STRING NULL,
    -- column_id: 741a786b-c2d7-476c-b9f5-435028c19146
    transaction_count BIGINT NULL,
    -- column_id: 0d5b5caa-7196-400b-b77d-086dd97edddc
    total_transaction_volume DECIMAL(18,4) NULL,
    -- column_id: ba6be937-f6ae-40b8-b6de-bbcfa525e3c5
    avg_transaction_amount DECIMAL(18,4) NULL,
    -- column_id: af7470c6-7410-4802-9011-a428012b32cb
    fraud_transaction_count BIGINT NULL,
    -- column_id: 11097801-8a33-43b7-86c5-6738c70e223e
    fraud_amount DECIMAL(18,4) NULL,
    -- column_id: a72096e6-01f2-469c-a376-9fed65968a50
    unique_merchants STRING NULL,
    -- column_id: 354993f0-5fff-41d4-9c5f-a382435f831c
    unique_categories STRING NULL,
    -- column_id: 05e9367a-d185-46db-a1a8-ea55af38059f
    international_transaction_count BIGINT NULL,
    -- column_id: f90476e9-6794-4ab4-a133-82ea4ca808bd
    active_account_count BIGINT NULL,
    -- column_id: 0a691caa-1726-44d8-8627-59397fdb4182
    total_balance DECIMAL(18,4) NULL,
    -- column_id: 8a443b40-71f3-499a-b71b-a96ad0a42aa6
    avg_balance DECIMAL(18,4) NULL,
    -- column_id: f9bfa0d2-29c0-4586-a272-26d0f7403bd3
    past_due_account_count BIGINT NULL,
    -- column_id: 2b4d268b-3acc-4a78-8276-80375b5d687f
    fraud_rate_pct DECIMAL(18,4) NULL,
    -- column_id: b0e2720d-ccca-42bd-93f3-3c3a10f5369a
    customer_count BIGINT NULL,
    -- column_id: 6b0d1608-698e-4031-806b-0484f97b135d
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(customer_key)
DISTRIBUTED BY HASH(customer_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
