DROP TABLE IF EXISTS finance_analytics_dm.ods_accounts;
-- table_id: c1ff2410-400e-4627-adac-98d36dbc7039
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_accounts (
    -- column_id: dbddefee-3ccb-4efa-9f5c-87ce72e4cf1c
    account_id BIGINT NULL,
    -- column_id: 306c4b00-b3c2-4c25-8086-d84c8504f7ca
    customer_id BIGINT NULL,
    -- column_id: e3b60249-a239-47a2-9857-f0a5bd4604d1
    product_id BIGINT NULL,
    -- column_id: 4561fcdc-617f-42bc-bc01-a345bc918fde
    account_number STRING NULL,
    -- column_id: ef8163dc-f89f-4dbb-97a0-8411b1e1d573
    account_status STRING NULL,
    -- column_id: 79b229fc-de94-47d5-bca2-ad15b7fb80bb
    open_date DATETIME NULL,
    -- column_id: 354f03fd-7256-40b7-8a1c-f536debff9dd
    close_date DATETIME NULL,
    -- column_id: d885d2a3-5bb1-45ae-99ac-4514bbb670f1
    current_balance DECIMAL(18,4) NULL,
    -- column_id: d341886f-19d5-49ec-add8-b06f7aa2d283
    available_balance DECIMAL(18,4) NULL,
    -- column_id: 921e1c82-e86a-4c29-83d3-73832feac66f
    credit_limit DECIMAL(18,4) NULL,
    -- column_id: d6f04568-4cb6-4e7c-8e0c-291a0d7d2760
    currency STRING NULL,
    -- column_id: eca39344-8a80-405b-be4a-690d999fab05
    interest_rate DECIMAL(18,4) NULL,
    -- column_id: 30434706-9abd-4d75-851e-479e29c45f71
    minimum_payment STRING NULL,
    -- column_id: 0d366824-5c36-4953-aa93-47237bd50846
    payment_due_date DATETIME NULL,
    -- column_id: 22b3b0c6-53df-48c5-920d-54348249c476
    last_statement_date DATETIME NULL,
    -- column_id: 8a6ed6f8-e30b-4ecc-8d69-bb4bd1a74548
    autopay_enabled STRING NULL,
    -- column_id: 0f899d44-8875-40af-82b5-02106fe25c7a
    overdraft_protection STRING NULL,
    -- column_id: ac89b8df-0913-46bf-8e52-bfc7bb908b51
    primary_account STRING NULL,
    -- column_id: 1dda0022-6d1c-483f-8396-7b43b399f758
    created_at DATETIME NULL,
    -- column_id: 6e86d848-1ec8-4fad-90b5-2ce4b7107f0f
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(account_id)
DISTRIBUTED BY HASH(account_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
