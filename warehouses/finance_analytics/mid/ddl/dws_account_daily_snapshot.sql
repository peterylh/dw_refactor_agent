DROP TABLE IF EXISTS finance_analytics_dm.dws_account_daily_snapshot;
-- table_id: 7b5b95fb-b94b-4a56-992d-56689ab8fe48
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_account_daily_snapshot (
    -- column_id: e245a985-7596-4995-b9ff-475b82de3910
    account_key CHAR(32) NULL,
    -- column_id: 2dcb7981-725a-4cb4-8b77-be71c75057c5
    snapshot_date_key CHAR(32) NULL,
    -- column_id: f5d4dc6d-e039-4deb-a106-b672dd6b7cbb
    customer_id BIGINT NULL,
    -- column_id: 21e5820b-f5dc-4380-afb0-03f3050192a8
    customer_key CHAR(32) NULL,
    -- column_id: 029a017b-9a16-4e14-a218-3e86a84aa77e
    product_key CHAR(32) NULL,
    -- column_id: 6bfd268b-b199-4c71-90e8-742068eadfd8
    snapshot_date DATETIME NULL,
    -- column_id: be85bb5a-582a-4e79-b137-83a1cd3728fb
    current_balance DECIMAL(18,4) NULL,
    -- column_id: 36ae163f-c468-4feb-a1b1-412e5983fd79
    available_balance DECIMAL(18,4) NULL,
    -- column_id: 8a3eb023-a4a7-431e-9319-3aa973b84157
    credit_limit DECIMAL(18,4) NULL,
    -- column_id: 0efd68d8-1263-47f1-9798-a78f318e3267
    credit_utilization_pct DECIMAL(18,4) NULL,
    -- column_id: f7dc4dd1-0859-492a-9490-282efbaef33e
    account_age_months BIGINT NULL,
    -- column_id: 8fd13524-1fc0-48a1-a138-5d8c13210c0e
    active_account_count BIGINT NULL,
    -- column_id: 319ae59c-aad2-4238-9913-5fd86c14112b
    closed_account_count BIGINT NULL,
    -- column_id: 3aaa1adf-539a-4e74-b31b-3d936f281264
    dormant_account_count BIGINT NULL,
    -- column_id: 585db89e-97ae-4be4-9cc2-7d50b82a73da
    past_due_count BIGINT NULL,
    -- column_id: ab6f4e84-71ec-4c14-9c8c-e0fdff29cb5b
    near_limit_count BIGINT NULL,
    -- column_id: 3a982976-7ec7-434e-b46d-f3f96a1acad0
    daily_transaction_count BIGINT NULL,
    -- column_id: 2cd09f4e-fa91-46d3-a365-0b83d60cc6cc
    daily_transaction_amount DECIMAL(18,4) NULL,
    -- column_id: 3c8daebe-c470-4bc1-a1c1-f92174e9446e
    daily_debit_count BIGINT NULL,
    -- column_id: 2c8c850b-8a5b-463f-9f24-8c4da11bb047
    daily_credit_count BIGINT NULL,
    -- column_id: f8d63cef-d0af-4f39-9bb4-49bb4587d527
    account_count BIGINT NULL,
    -- column_id: afea751e-2c5b-4b5d-9257-a6af39b3b370
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(account_key)
DISTRIBUTED BY HASH(account_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
