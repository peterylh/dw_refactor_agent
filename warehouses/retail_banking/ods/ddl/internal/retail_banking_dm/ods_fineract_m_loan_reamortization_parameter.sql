-- ODS mirror of Apache Fineract m_loan_reamortization_parameter (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_reamortization_parameter;
-- table_id: 05baa1c5-a998-4394-9d41-8599545835b5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_reamortization_parameter (
    -- column_id: 027a755c-1781-4a49-bac9-ef6c7a6e364b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6691a976-d53a-4343-9ccc-0b5db57657a0
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 75e5615d-296f-49a6-9467-c12c531e2a61
    `interest_handling_type` VARCHAR(40) NOT NULL COMMENT 'Fineract source column interest_handling_type',
    -- column_id: 4ab45feb-fcc3-43f7-969a-092d3204d3bb
    `reamortization_reason_code_value_id` INT NULL COMMENT 'Fineract source column reamortization_reason_code_value_id',
    -- column_id: ee8c1baa-671b-4f96-8ac7-405e6ee645f0
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 086e4a82-ebb4-4b81-a72a-4a5ad4f83f8e
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: b195cf02-a3ce-4d5b-9596-70ffab20815b
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 652cd286-d9b7-4e96-bf51-167ea5e2d809
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c1b3a958-dcaa-43ab-bb6a-f2fc40bb7bee
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
