-- ODS mirror of Apache Fineract m_loan_term_variations (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_term_variations;
-- table_id: 5eac9922-6e71-40cb-91a3-4a6a8af41e19
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_term_variations (
    -- column_id: 1aed09f7-e38e-4537-8fd9-e87d9cb5d44c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e7cd9c3a-857d-4e09-a0f0-b2b71b0cd3a6
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: cc0a4b3d-caf4-44be-87d7-7315d954a760
    `term_type` SMALLINT NOT NULL COMMENT 'Fineract source column term_type',
    -- column_id: c87d19c4-6de7-4359-89f0-1af85687ea97
    `applicable_date` DATE NOT NULL COMMENT 'Fineract source column applicable_date',
    -- column_id: 9de0393d-a609-4f90-96a2-7025ee704a1c
    `decimal_value` DECIMAL(19,6) NULL COMMENT 'Fineract source column decimal_value',
    -- column_id: bca0ab2d-d53b-42cd-b278-4e86099fe37f
    `date_value` DATE NULL COMMENT 'Fineract source column date_value',
    -- column_id: b02ccc89-0931-4d65-b56f-20b3c0ca1d1b
    `is_specific_to_installment` BOOLEAN NOT NULL COMMENT 'Fineract source column is_specific_to_installment',
    -- column_id: 09748ab7-e717-4fd0-9611-808c6f5c97ff
    `applied_on_loan_status` SMALLINT NOT NULL COMMENT 'Fineract source column applied_on_loan_status',
    -- column_id: e22f7d17-ecb5-4ee6-99e9-daa05e863aef
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 6a12c7f6-bc6b-4914-8e13-3a3a3a9269ee
    `parent_id` BIGINT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: d80fef17-0623-443f-ba87-c3262b477947
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: a9e67624-b029-4762-af11-de80b5e8ea93
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 185f5866-127a-482c-a5d5-e1110e362c00
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 611d90e8-aa99-4774-a12f-03f4f9de2370
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 5899daa3-19d4-42b3-b453-3b3321c2b5c1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
