-- ODS mirror of Apache Fineract m_loan_reage_parameter (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_reage_parameter;
-- table_id: f0565def-bdbe-4f6a-871b-4494a3ec0f06
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_reage_parameter (
    -- column_id: ac4e222c-4e2f-4708-8953-a12d3067ad02
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 32adaa40-5fce-43a6-a3c2-09601cf09dad
    `frequency_type` VARCHAR(100) NOT NULL COMMENT 'Fineract source column frequency_type',
    -- column_id: c3859604-dff5-4b35-8a78-46430ff66d48
    `number_of_installments` SMALLINT NOT NULL COMMENT 'Fineract source column number_of_installments',
    -- column_id: 7a6821cd-d3fd-4f42-a84b-0d58a9149abe
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 42f4af55-2051-433e-adbf-687644a56289
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: f6ebb62d-c34c-4d02-9318-108ec7089dd1
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a50b39d3-72c9-4490-88c5-d91673f6f08e
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 13a917e8-1927-4b37-9a20-99f9ed6d7cc5
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 238cee67-a3e6-405d-a7d7-aa9e037c475b
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 9e57bcab-ca99-48bc-81f1-4fcc5cc7d9f2
    `frequency_number` SMALLINT NOT NULL COMMENT 'Fineract source column frequency_number',
    -- column_id: 12b40e72-f9e4-4264-9821-444537e4960d
    `interest_handling_type` VARCHAR(40) NOT NULL COMMENT 'Fineract source column interest_handling_type',
    -- column_id: 766c65df-1263-442f-aab8-1b1de7583d91
    `reage_reason_code_value_id` INT NULL COMMENT 'Fineract source column reage_reason_code_value_id',
    -- column_id: b8fa3f31-c900-4f7c-86c1-d25a72046515
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
