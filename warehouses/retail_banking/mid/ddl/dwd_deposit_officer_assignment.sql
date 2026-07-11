-- DWD generated from m_savings_officer_assignment_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_deposit_officer_assignment;
-- table_id: e0d1b01c-ccd4-4e23-9f94-f642e3ce967a
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_deposit_officer_assignment (
    -- column_id: b9df81d2-18e5-4d56-9be1-a2752c79dc47
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2de48856-b004-4293-a58c-ea513bb56ec2
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: fca3cee0-67ab-40c9-b8cb-0212d35d73ec
    `savings_officer_id` BIGINT NULL COMMENT 'Fineract source column savings_officer_id',
    -- column_id: 1377d81d-c712-4092-8e4a-bd90d32dccdb
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: c43f96d0-b906-49a1-b197-4704fc453438
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 70f48159-3c93-4adc-8894-db048a7c33bb
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: b6e91cdb-7efc-4ed9-b6cd-2738046cb837
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 7d58ad9f-502f-4c21-b0b0-ff2886f99582
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 05ded848-dec1-4ef6-ba17-0a006ac034af
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 239ec7bb-1ab4-483f-9222-23312a365781
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 45d47ccc-d847-41b7-b092-6bda967ccf78
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 22e68e3b-aeb9-4b49-b21c-b04694723b7b
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 7f8bc9ae-e482-42be-9c5f-0a31ac6fa03b
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
