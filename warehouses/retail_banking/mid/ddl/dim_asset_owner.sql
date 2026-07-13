-- DIM generated from m_external_asset_owner
DROP TABLE IF EXISTS retail_banking_dm.dim_asset_owner;
-- table_id: 218162b9-7fad-4170-8c5b-4f2f92f40562
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_asset_owner (
    -- column_id: f644b2d5-a0bf-4b93-ba4a-b1cf7a558cf2
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: fef1aaa0-4496-44af-83c4-259df5e1a11e
    `external_id` VARCHAR(100) NOT NULL COMMENT 'External id of asset owner',
    -- column_id: 2f0a5f76-7483-40ac-a3b5-87f89575f3b9
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 1e93399b-7875-4eed-93c9-53abf702661b
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 472a48a1-67b0-4089-a19f-dba081d602e1
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 89a604ad-9e6d-4c6a-9610-2e9a3b56db76
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: ee8d3995-6b8f-4897-88be-5248fd1f73b6
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
