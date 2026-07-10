DROP TABLE IF EXISTS finance_analytics_dm.dim_account;
-- table_id: e7ef8157-7a84-4421-9532-3ecc54038bbd
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_account (
    -- column_id: 0cc313f7-1b49-4fd0-a594-e655349258f5
    account_key CHAR(32) NULL,
    -- column_id: bbbcff9d-764b-4851-94f0-ebe0d5b21af9
    account_natural_key BIGINT NULL,
    -- column_id: 062b7464-bd14-46d4-b73a-7caa08a15847
    customer_id BIGINT NULL,
    -- column_id: 331fc8ad-6665-4efb-832e-e60ce840913d
    product_id BIGINT NULL,
    -- column_id: ac01e904-db93-4159-b26f-0cd64af63b5f
    account_number STRING NULL,
    -- column_id: d9537610-252a-4ab9-8d83-f5525eefede7
    account_status STRING NULL,
    -- column_id: 60d13573-99eb-43ef-a397-f12621b07a89
    open_date DATETIME NULL,
    -- column_id: e1170277-4d94-4f50-a26b-d5eb27665124
    close_date DATETIME NULL,
    -- column_id: ced2f1fa-67b8-489f-8651-df08f99638ce
    account_age_months BIGINT NULL,
    -- column_id: 0e7a8a04-e33c-4732-84c4-d4ff19741ab3
    is_active BOOLEAN NULL,
    -- column_id: c60cfb84-5aa5-4537-a7e6-7e5d6c9d5123
    is_closed BOOLEAN NULL,
    -- column_id: 4daaf4a5-8388-49ce-be73-5a06cb855b8a
    is_dormant BOOLEAN NULL,
    -- column_id: f5002e78-3a38-4e2d-b073-ff449e48cc19
    current_balance DECIMAL(18,4) NULL,
    -- column_id: a0e2d830-c280-4911-8816-daff5d8a322b
    available_balance DECIMAL(18,4) NULL,
    -- column_id: 33ad0a0e-d84a-4122-9927-f9c27d34f09c
    credit_limit DECIMAL(18,4) NULL,
    -- column_id: dc24cbfd-e7d0-42ac-9d9f-48b80f5a9ffb
    credit_utilization_pct DECIMAL(18,4) NULL,
    -- column_id: 7744c972-75d7-466b-919f-1c2c81fdad89
    balance_category STRING NULL,
    -- column_id: 691b0378-c8c0-4afd-9c7d-b5be8ab655a6
    currency STRING NULL,
    -- column_id: 626699d9-5302-4062-93d6-bb958b71fb70
    interest_rate DECIMAL(18,4) NULL,
    -- column_id: 1cbd33ad-ef4b-42cd-88c3-04bf1a4303a8
    minimum_payment STRING NULL,
    -- column_id: 619d6f65-672e-434f-83fe-15e1e30159e6
    payment_due_date DATETIME NULL,
    -- column_id: fed6c26d-d243-4e5f-8c41-2ff77ead881b
    last_statement_date DATETIME NULL,
    -- column_id: 6a030697-4491-4974-86c2-86aee740db51
    autopay_enabled STRING NULL,
    -- column_id: fcb39b36-4d7f-4d0e-8ea8-8993059680db
    overdraft_protection STRING NULL,
    -- column_id: 9f7a859d-fa06-4609-a785-b140f72d7415
    primary_account STRING NULL,
    -- column_id: 252cd362-e2fa-43a5-a9f8-0351af9f1a8d
    is_past_due BOOLEAN NULL,
    -- column_id: 3b1c8ade-3b8e-4c04-a1b9-1d50ca63dc6e
    is_near_limit BOOLEAN NULL,
    -- column_id: d9b1ebca-0ec8-4258-b95e-749d0944c7ea
    effective_date DATETIME NULL,
    -- column_id: 5c83efbe-9afe-41cf-b265-b5efb97c50c2
    expiration_date DATETIME NULL,
    -- column_id: 41502c24-c1af-4efd-b200-6428ef204a8b
    is_current BOOLEAN NULL,
    -- column_id: 8f8e876f-eb16-4952-80d1-d4fba0593a8b
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(account_key)
DISTRIBUTED BY HASH(account_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
