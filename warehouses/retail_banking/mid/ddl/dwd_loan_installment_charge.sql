SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_installment_charge
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_installment_charge;
-- table_id: e8c83fe7-35a5-4404-bf0a-3683c4ce569b
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_installment_charge (
    -- column_id: a30ac595-f170-40b0-baf0-e8a1b383c4df
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 99b6d395-e009-4f5e-94e8-141f08f8e260
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 927233f6-48be-4a28-8507-21cd28da91d2
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: 2cce2d2b-8fde-4967-ac3d-de2d1a5e4215
    `loan_schedule_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_schedule_id',
    -- column_id: 8c1e9483-e41c-4d02-a4a7-f364a7f19189
    `due_date` DATE NULL COMMENT 'Fineract source column due_date',
    -- column_id: c7873c2c-4c9e-4f5f-9ac6-de407bed7a88
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: af038a2d-400a-4779-ac48-c107e0d6a4f0
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: 0c9eb564-37d8-4fc2-a6cc-97738f0de598
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: c892c4f3-73fc-4354-a68c-a00a70254e25
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: 3cd9b86e-f356-46f1-99f1-ea95c3243cb3
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: 282442ed-7d74-4f29-a85d-acae99f3d919
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: 610930ec-495d-4672-80f4-466cfc4aad0d
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: c52cacb8-0dd3-4a26-a5ac-9f2af079ac5a
    `amount_through_charge_payment` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_through_charge_payment',
    -- column_id: 91d278cc-033d-4f29-b548-6925ad8c3eea
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: f7f77c20-cf5e-4ba7-89be-db4843279e85
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
