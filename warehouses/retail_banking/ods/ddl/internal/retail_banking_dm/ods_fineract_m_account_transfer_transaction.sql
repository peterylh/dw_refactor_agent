-- ODS mirror of Apache Fineract m_account_transfer_transaction (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_account_transfer_transaction;
-- table_id: 35f942f2-0738-4be9-8858-682a46138fb3
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_account_transfer_transaction (
    -- column_id: e6d27d2a-ec7f-4eb1-8bc8-82da07edaac1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0cc952d5-9af3-4b70-95d5-b52db10500a2
    `account_transfer_details_id` BIGINT NOT NULL COMMENT 'Fineract source column account_transfer_details_id',
    -- column_id: 8e2f873e-f6da-49e4-bc99-75609a5bd46d
    `from_savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column from_savings_transaction_id',
    -- column_id: bd9e11ce-996f-4334-9a9a-cf5e848a9be0
    `from_loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column from_loan_transaction_id',
    -- column_id: ad6468d3-588f-42b2-8412-f3a1800e4952
    `to_savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column to_savings_transaction_id',
    -- column_id: 1beed953-983c-4258-bf4f-d69cd1ef8710
    `to_loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column to_loan_transaction_id',
    -- column_id: 14885121-488c-433e-ba03-8bc963671d7a
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 4df42c5e-07d0-4766-bc01-ce205feb0d9a
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: f19dd21c-f532-47a6-a47e-f35ee1a4437b
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: c0bb18c9-9108-4697-97ae-aeaf7eee0cc0
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: f7d99ae9-4880-4ead-af37-f3b6e3c04625
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: a5c8a282-40a8-47d9-9361-6cfa28788d7b
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 630538d4-5c11-4a2f-ae5c-bfde93b4ea25
    `description` VARCHAR(200) NOT NULL COMMENT 'Fineract source column description',
    -- column_id: 9ade84c0-ded4-43ca-a3c2-3dfc293647cf
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
