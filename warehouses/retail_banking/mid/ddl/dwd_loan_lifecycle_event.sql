-- DWD generated from m_loan_status_change_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_lifecycle_event;
-- table_id: 41e86604-99ff-483b-9e0b-bb57eae47cb3
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_lifecycle_event (
    -- column_id: cc4e7b10-cc6f-4de3-970a-03a37b2acd14
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1e857d57-5c0b-4129-8744-1fcec6460e8d
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 65e5b181-da18-4a8c-bc2b-24c8b1132d29
    `status_code` VARCHAR(255) NOT NULL COMMENT 'Fineract source column status_code',
    -- column_id: 861cb6f3-f1b1-40bb-9a60-20174a9dc3a7
    `status_change_business_date` DATE NOT NULL COMMENT 'Fineract source column status_change_business_date',
    -- column_id: 088b8259-d5af-4b9c-a2e0-98e562e90eb8
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: c4a4d066-8177-4c4e-9884-4e00c9de7a05
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 086a62aa-e1cc-426b-9c18-4396c89d01b6
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 3e334d26-7ed3-4e02-92d0-d9a94d404a73
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 4e36d4f5-92e3-48b0-9ce4-30718a3ffdc0
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: c30dea5a-a704-4fdd-a483-1b89c4a50841
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
