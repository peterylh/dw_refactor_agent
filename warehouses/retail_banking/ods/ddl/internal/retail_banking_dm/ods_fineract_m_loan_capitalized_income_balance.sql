-- ODS mirror of Apache Fineract m_loan_capitalized_income_balance (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_capitalized_income_balance;
-- table_id: d075d01d-63f1-480e-b50e-95ece9d64083
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_capitalized_income_balance (
    -- column_id: a05aecaf-c1ca-414b-bb70-b1d3271c39a1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ad6fef7e-9cbf-468d-8922-97a121d18e40
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: fd054404-3e3f-43bd-8bac-0c45be6dbc52
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 5b781aeb-88c5-4751-8189-ce50beed5aa6
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 70f0eee9-3f98-4740-b149-4aedf8d7c9e2
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: b0485239-4f39-4785-83c5-826dffe38349
    `date` DATE NOT NULL COMMENT 'Fineract source column date',
    -- column_id: a6b06d49-403c-4a28-be09-79aa717bcd6e
    `unrecognized_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column unrecognized_amount',
    -- column_id: faf00877-f9ab-4848-9774-dc6351f4149a
    `charged_off_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column charged_off_amount',
    -- column_id: 7a854306-d473-41fa-a82a-9be7d17e5d36
    `amount_adjustment` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_adjustment',
    -- column_id: 8cf98f92-5e29-4743-9981-c0f49c96d522
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 0a738bc5-2867-4cbc-8ce2-31d3edb4654a
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c58dbb8f-033d-4ce8-8d64-7e98351fee8b
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a48f0916-a4e9-4a9e-b0cb-3ae90ee379b9
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 85b28cbb-109c-4b25-9818-96f778194a6c
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 90f68ab2-5947-4c17-baa6-d7c473d74c20
    `is_closed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_closed',
    -- column_id: e86c8426-cd27-4937-871f-b854b54c7b24
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
