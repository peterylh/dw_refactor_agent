-- ODS mirror of Apache Fineract m_loan_buy_down_fee_balance (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_buy_down_fee_balance;
-- table_id: 3000e221-d053-4a69-ae01-e8206e47dc6c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_buy_down_fee_balance (
    -- column_id: f1d5db4b-5181-4f76-be4f-6ad716bfb254
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2b34159a-fd56-43f2-88c9-fe06ddd216f8
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: c62d9bdc-b579-4e45-ab23-2badf4ee5cc7
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 77ce02f6-8258-4213-a9ce-332c0080fa25
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 8c1d1d0d-7817-4b52-b439-359fbd4ec924
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 9ff75be6-6e68-4d7e-ab7f-969bf6f25e2e
    `date` DATE NOT NULL COMMENT 'Fineract source column date',
    -- column_id: f6457883-e22e-4df9-8d4c-a34a91683f83
    `unrecognized_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column unrecognized_amount',
    -- column_id: fef5b860-47e6-49e5-9214-f36e02973ceb
    `charged_off_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column charged_off_amount',
    -- column_id: 6beefa58-ec8d-4878-8334-7274ba4ddbd9
    `amount_adjustment` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_adjustment',
    -- column_id: 3cfc4e7d-5b5c-401d-aea6-4df789d34bed
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 63c5b3c8-73cd-4d09-a34b-a22bcdac16fb
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 9fe10894-2adf-4543-9fea-c85e6891d665
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 73da47c6-46e6-448e-96af-42946a2e75f0
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 984c2c0f-f361-4eea-88b8-3430bfd34b88
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 76ac2f5f-b8d0-4c38-84e8-26531b33cb8b
    `is_closed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_closed',
    -- column_id: bb1e8cda-ce6f-411c-8c47-04472611ade4
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
