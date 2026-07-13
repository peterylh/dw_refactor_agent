-- ODS mirror of Apache Fineract m_loan_originator (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_originator;
-- table_id: f4b9d42f-a91f-47ce-8ee2-c400a0a61acc
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_originator (
    -- column_id: 29ea590d-1115-46b2-b934-6f56f7f5e4d3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 07e6273b-c823-483e-bf3a-eeddaaae5eed
    `external_id` VARCHAR(100) NOT NULL COMMENT 'Fineract source column external_id',
    -- column_id: bd6e564e-35d0-4e6c-9bcd-8e9d3b6d42d6
    `name` VARCHAR(255) NULL COMMENT 'Fineract source column name',
    -- column_id: 2e5ea0cc-46ac-4171-bfca-6af9818b7a93
    `status` VARCHAR(20) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: e6e29134-0572-4b35-8bcd-5befcede9803
    `originator_type_cv_id` INT NULL COMMENT 'Fineract source column originator_type_cv_id',
    -- column_id: 8428e12c-befa-4339-bbc2-036bc1ff0252
    `channel_type_cv_id` INT NULL COMMENT 'Fineract source column channel_type_cv_id',
    -- column_id: c7e0fb06-1d75-4b1e-9270-16428bf11482
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c63d096d-0308-434e-a811-83a6cd49a246
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 6828609b-a913-430e-8153-062ad3d9f51c
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c6b1469e-4d88-454e-af8c-991c5efbddf5
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 8d880b1d-adda-4e3f-8bd4-6fc746503fb9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
