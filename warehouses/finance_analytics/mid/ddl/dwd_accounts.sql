DROP TABLE IF EXISTS finance_analytics_dm.dwd_accounts;
-- table_id: 17301a1a-9ad0-44a4-8289-427ebf301e4d
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_accounts (
    -- column_id: 90c3215f-d797-4b9a-b301-ff52321086ba
    account_id BIGINT NULL,
    -- column_id: 5a4abbb3-d427-49b4-b558-9913a334e46e
    customer_id BIGINT NULL,
    -- column_id: 05a8c8f7-3494-41c7-87fa-ab8717e283fa
    product_id BIGINT NULL,
    -- column_id: 205e881c-161f-4a51-85f3-1864739bec7f
    account_number STRING NULL,
    -- column_id: eeb06467-ca76-494b-8602-596325071637
    account_status STRING NULL,
    -- column_id: 1661926f-5d41-4d61-843a-9783d725e5a0
    open_date DATETIME NULL,
    -- column_id: 54ad3307-191c-40f5-8b22-326688c708f9
    close_date DATETIME NULL,
    -- column_id: 17bdf879-1ce9-48ec-82ac-3184b8b433b9
    account_age_months BIGINT NULL,
    -- column_id: 80bad0bb-5fa8-4f0f-8685-707b64773f56
    is_active BOOLEAN NULL,
    -- column_id: 43294743-48cc-4691-bd85-5b85025eb60a
    is_closed BOOLEAN NULL,
    -- column_id: 18d6a690-a922-4166-8cb7-42f454ca2cb3
    is_dormant BOOLEAN NULL,
    -- column_id: cada231e-f958-429c-a4f9-ef2e7b8d5b7b
    current_balance DECIMAL(18,4) NULL,
    -- column_id: b7f9095f-ea0a-4a38-82ab-21fb4177a3b7
    available_balance DECIMAL(18,4) NULL,
    -- column_id: 22faa1ec-b94a-46ec-9848-08fe51d98e55
    credit_limit DECIMAL(18,4) NULL,
    -- column_id: 605d86b9-4915-489a-a157-8ebc4be98db7
    credit_utilization_pct DECIMAL(18,4) NULL,
    -- column_id: aadff14e-e71b-49d9-93f5-ccf0b1cd969a
    balance_category STRING NULL,
    -- column_id: f87defd9-29c6-4c69-b4e8-6f5afe6af37a
    currency STRING NULL,
    -- column_id: 2502cbd1-2392-43cd-8689-67a3facac930
    interest_rate DECIMAL(18,4) NULL,
    -- column_id: 92d7d352-9896-4987-bb4a-92e1464abf8c
    minimum_payment STRING NULL,
    -- column_id: 71dc6f62-d517-4a40-b576-57d246ef43ca
    payment_due_date DATETIME NULL,
    -- column_id: 947b1437-a2a3-47db-85b7-d5f42a4f9ff7
    last_statement_date DATETIME NULL,
    -- column_id: 75520fe5-6b8b-4692-88aa-9b027d674bd7
    autopay_enabled STRING NULL,
    -- column_id: 1801a628-5999-4934-b9a4-8e8892e24b86
    overdraft_protection STRING NULL,
    -- column_id: e41cabc0-c488-46a2-881c-d14ae19b5b9f
    primary_account STRING NULL,
    -- column_id: eae53f9c-d27d-407e-af3b-2bf08e156121
    is_past_due BOOLEAN NULL,
    -- column_id: 45f6399b-e03f-4b9d-86e2-02547bffae7a
    is_near_limit BOOLEAN NULL,
    -- column_id: 8e88a08e-2b7b-4a9a-bd9d-4bb899cdec3a
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(account_id)
DISTRIBUTED BY HASH(account_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
