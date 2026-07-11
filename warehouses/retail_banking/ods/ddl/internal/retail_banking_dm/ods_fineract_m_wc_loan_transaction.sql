-- ODS mirror of Apache Fineract m_wc_loan_transaction (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_transaction;
-- table_id: 127df2a8-60b2-4445-8ab2-3c3aed73394d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_transaction (
    -- column_id: f512cf03-505d-4adb-9607-b162e5d7f3a4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bf9b7f09-c51a-46ad-a05a-f2bf20b12bc9
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 1f7ce9b4-8220-4bf2-a57f-9dd8a98b6264
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: 28294b12-a260-48b3-b3e7-89e3472d4ae6
    `classification_cv_id` INT NULL COMMENT 'Fineract source column classification_cv_id',
    -- column_id: 07c99f6c-4d62-46dc-b4ad-adad9df36f58
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 89feb49c-92c9-401a-b855-6cb9ba7f6466
    `transaction_type_id` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_id',
    -- column_id: 921a7246-c76c-4e10-806f-8bccbeecad69
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: a0efffb2-d2a0-4a4c-9b3c-3772ae7f0737
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: ec327f29-af49-49eb-b3c8-8f1687806351
    `transaction_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column transaction_amount',
    -- column_id: f6be5a84-d726-446c-9841-862086fba201
    `version` SMALLINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 49be15a3-a0f4-442b-a9f0-8fb2a027a3b7
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 92bf24d0-1ff2-4f79-ba1f-714c8baf7fed
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 3243bdc8-9eb7-4a46-b58e-d4e181db4682
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: dca45546-ca5d-41e5-931a-e139e5781758
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 675a52e1-7984-4e1c-b4f1-f7761d9814c9
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 1d0a8c64-0102-40bf-b047-333ad01c5f06
    `reversal_external_id` VARCHAR(100) NULL COMMENT 'Fineract source column reversal_external_id',
    -- column_id: 7af13622-88c4-439d-a661-7f667634ea3f
    `reversed_on_date` DATE NULL COMMENT 'Fineract source column reversed_on_date',
    -- column_id: 751e090d-496c-4075-a426-3e45aeeff3af
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
