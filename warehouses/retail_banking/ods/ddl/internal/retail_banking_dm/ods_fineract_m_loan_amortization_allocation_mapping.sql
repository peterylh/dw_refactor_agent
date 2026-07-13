-- ODS mirror of Apache Fineract m_loan_amortization_allocation_mapping (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_amortization_allocation_mapping;
-- table_id: fc9f55d6-cdc9-4a61-b096-3e2cca88c6fd
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_amortization_allocation_mapping (
    -- column_id: 4b0c7544-0b3b-4325-aa54-ec3969fd6a6f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e07deb85-c58e-4a66-bc36-b28ea40feb54
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 898b3203-bf12-43ed-bc00-3bb4b460ea18
    `base_loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column base_loan_transaction_id',
    -- column_id: 275a5195-6b59-4049-af36-9241fc848901
    `date` DATE NOT NULL COMMENT 'Fineract source column date',
    -- column_id: 01081856-cc88-470f-964c-fda94c4011ed
    `amortization_loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column amortization_loan_transaction_id',
    -- column_id: cf42285a-414e-4fe3-a777-99873232a167
    `amortization_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column amortization_type',
    -- column_id: 42801ef5-89bd-4cc5-a2ef-b6a05f5fbf6c
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 7b603f4e-a7ba-4496-83af-70a66172d8a8
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: a4f9f477-eb1d-4e65-80db-f39285bd3644
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: a426ec8e-d28a-4859-952c-be745c34dc09
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 00af0ed0-a5b7-4511-866b-4be3aef45a29
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 705de3ed-b9a7-42f1-98d1-651807a00502
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
