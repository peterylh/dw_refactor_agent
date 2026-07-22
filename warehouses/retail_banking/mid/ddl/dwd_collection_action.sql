SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_delinquency_action
DROP TABLE IF EXISTS retail_banking_dm.dwd_collection_action;
-- table_id: f822eda7-77d5-4993-8b5c-bc07953aa66b
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_collection_action (
    -- column_id: aa8a749b-a1b3-433f-9ea8-0dd9a8c92ebe
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f708260d-7676-49eb-9cce-0f9d89b082d1
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: f2c735fe-b050-4236-9bff-29e53a8fa414
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 7a32378a-ccdb-4516-a942-96f94a6ee1a6
    `action` VARCHAR(128) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: 1d539bec-32f7-4f26-aebb-a5457ad2bcde
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 89cd3cec-33c6-426b-a772-125e00b49346
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 1660b57a-5cb0-4767-beeb-8f7156a11ef4
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: bfc9f495-2470-40be-ae3e-fb1ddb0242df
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: e78aa288-5305-46c4-b623-4a46aa802040
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: f40de91d-92a7-4251-b175-c7a99dbd42aa
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 0f0faf0b-43a9-49a7-a69d-43a749c46773
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
