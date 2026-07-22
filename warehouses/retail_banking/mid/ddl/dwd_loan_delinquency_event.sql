SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_delinquency_tag_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_delinquency_event;
-- table_id: 8daeaef7-344f-41c5-bee8-aab041e0795b
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_delinquency_event (
    -- column_id: b4735132-b2f6-482f-8e81-cef19697daad
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7d53e052-4fb3-48c6-a971-14eab029c04e
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 8c90157b-ce0f-4c7b-93b4-39b3b9988da2
    `delinquency_range_id` BIGINT NOT NULL COMMENT 'Fineract source column delinquency_range_id',
    -- column_id: b33fb2ac-34fa-45dd-8319-c3b43453e2c8
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 197bc074-d87b-4dd6-b974-c97f65f5f2b5
    `addedon_date` DATE NOT NULL COMMENT 'Fineract source column addedon_date',
    -- column_id: 8d357a23-f1b4-4996-b8fa-878e80342af4
    `liftedon_date` DATE NULL COMMENT 'Fineract source column liftedon_date',
    -- column_id: 9e29d83e-32a8-46e5-9393-51d222d276e3
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: cdd6bf9c-4be4-4255-abe1-27ec2795572a
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 85d82c4d-741a-4864-9f51-3eac7d764f4d
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: f88a264b-3253-4508-a409-5cf64c1244fe
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: f3dbd500-4b56-40e4-8bc5-58bd493fdd4f
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: b7a1ea2c-06cb-438b-989a-006ac8f8111c
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
