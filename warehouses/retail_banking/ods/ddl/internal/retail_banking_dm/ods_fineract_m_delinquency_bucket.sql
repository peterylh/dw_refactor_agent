-- ODS mirror of Apache Fineract m_delinquency_bucket (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_delinquency_bucket;
-- table_id: c9ae75d8-5e5a-4d06-9e64-1e30e04454ee
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_delinquency_bucket (
    -- column_id: 7ef4d45c-d796-4b0e-aca3-0a5d305f43f6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f4f6b6d7-6e09-4c1a-87ec-88e77479997d
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: cc761ad3-a687-40a8-b0d2-1f029ac47ea0
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 9f2e6fcb-ac8f-4c27-99d0-aea44719df9b
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 193b7bb4-6cba-418b-881b-11bbe8a73240
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: c7fc94ad-441b-4517-9c5c-06736493edaf
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: e9267de2-4c81-47de-9031-f576c6129c98
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c21fb698-0df6-4c1d-aed5-32c0c5ed8bd8
    `bucket_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column bucket_type',
    -- column_id: 0c7a85d4-5dfc-4e9c-9d7a-667d5ca44f1b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
