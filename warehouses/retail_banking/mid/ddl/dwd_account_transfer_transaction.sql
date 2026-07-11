-- DWD generated from m_account_transfer_transaction
DROP TABLE IF EXISTS retail_banking_dm.dwd_account_transfer_transaction;
-- table_id: a050e64f-4159-42b9-b5c9-f8e9c7ed1409
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_account_transfer_transaction (
    -- column_id: feda5a9e-8634-41d5-8e52-06b296f9fa2a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7a1a8470-503e-45eb-bdcc-6d1529ee38ba
    `account_transfer_details_id` BIGINT NOT NULL COMMENT 'Fineract source column account_transfer_details_id',
    -- column_id: a51d72b9-8662-4e97-bf58-31fbd8179ddd
    `from_savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column from_savings_transaction_id',
    -- column_id: 8da0cd8b-5b61-4dec-aeda-ea65f3f3743e
    `from_loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column from_loan_transaction_id',
    -- column_id: 158c6bb3-8476-4e9f-9f05-b79cade01dca
    `to_savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column to_savings_transaction_id',
    -- column_id: 11d13001-e1fa-4e47-9f10-098c948ec89c
    `to_loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column to_loan_transaction_id',
    -- column_id: 8718ad84-6cf8-4da4-b435-9a7bf0c3822f
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 9dcefa21-0db2-41c8-bee7-574b0bc97d76
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 9a9c5bfc-00b3-422c-b2c7-9ef7d7c4719c
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: a9c47a88-e345-496b-99f9-1a41ead3a750
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: acf82fe9-537f-444d-a715-bcc5812b325f
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 7b5832bc-c967-4f8b-96c5-40198746e090
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: b3caa43d-9fde-4ed4-b373-b6eb50b6ddcb
    `description` VARCHAR(256) NOT NULL COMMENT 'Fineract source column description',
    -- column_id: fe57499d-2050-4d11-aaba-772db673dd11
    `from_office_id` BIGINT NOT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 12857d8e-86fc-4dcc-8a9a-7a8e4a50a802
    `to_office_id` BIGINT NOT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: 7d4db0c9-7f2b-44e4-979f-8260e4761396
    `transfer_type` SMALLINT NULL COMMENT 'Fineract source column transfer_type',
    -- column_id: 18ea527c-af2c-443b-8862-c4d4f70c7663
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 212c0430-4d4c-4743-bf9e-e3968cb9d01d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
