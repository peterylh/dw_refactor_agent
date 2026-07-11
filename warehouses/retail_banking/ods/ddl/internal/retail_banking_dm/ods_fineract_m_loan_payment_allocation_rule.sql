-- ODS mirror of Apache Fineract m_loan_payment_allocation_rule (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_payment_allocation_rule;
-- table_id: ad462d7e-6e27-4d1e-8d38-16828041fd5a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_payment_allocation_rule (
    -- column_id: e869dc6c-e577-4b09-8c6a-a82ba91e51b3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 50c4dd55-f2cb-47b9-943b-b9f9e72a3c5c
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: a0106ab5-3152-4258-9061-d15902c2a520
    `transaction_type` VARCHAR(255) NOT NULL COMMENT 'Fineract source column transaction_type',
    -- column_id: 1c05fb99-90df-48f0-8aad-381f0566dce0
    `allocation_types` STRING NOT NULL COMMENT 'Fineract source column allocation_types',
    -- column_id: be791ea8-46b0-4653-be9b-683783a19b02
    `future_installment_allocation_rule` VARCHAR(255) NOT NULL COMMENT 'Fineract source column future_installment_allocation_rule',
    -- column_id: dbc91fe4-d614-45a4-a9bb-2aa15214fee8
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 8d4cb5d5-4483-4a5e-9d20-0f4e3d905b00
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 3345ca50-f0d7-44b5-add3-42d03b9a0f39
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 179ecb19-2e26-4fff-978b-4a3715be6324
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 02b6e38b-0d34-4ac0-bc1d-19408c25666a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
