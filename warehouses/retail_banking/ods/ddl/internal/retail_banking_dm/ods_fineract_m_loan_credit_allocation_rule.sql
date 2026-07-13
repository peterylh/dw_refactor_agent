-- ODS mirror of Apache Fineract m_loan_credit_allocation_rule (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_credit_allocation_rule;
-- table_id: 971517b5-0ae3-43cf-b367-9d51a2d023d7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_credit_allocation_rule (
    -- column_id: 96329f4c-ee4e-4c61-85fb-86ad7a6e9ba8
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ee48f488-4fad-41f6-91ef-0c7567de5d5a
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 49e851dd-6f53-43c4-80f7-c2c6484214af
    `transaction_type` VARCHAR(255) NOT NULL COMMENT 'Fineract source column transaction_type',
    -- column_id: fca78828-f529-4f13-a4f8-a9623cd8484c
    `allocation_types` STRING NOT NULL COMMENT 'Fineract source column allocation_types',
    -- column_id: 578f4a29-e0b0-4e88-8c24-f3e4579ca053
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: e49844b4-9ecd-4587-9a3e-b9e887e05e5b
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 99ceb507-7730-44e7-abe0-69d7bac1b825
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c16ffdee-a15e-4242-b0c6-c22c99fb42f8
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: fa5f6192-b43f-4b9b-9c9b-c888e66460c6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
