-- ODS mirror of Apache Fineract m_client_identifier (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_identifier;
-- table_id: 3b541f71-a0de-4bb9-bc3d-c3cd47e4df8c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_identifier (
    -- column_id: bdb1325c-b41e-4541-b9ab-ebe2eb4a354a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9d706940-e500-47ef-93ff-30afe3eb7beb
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 792394b9-0e24-4666-b254-ea7194ec0848
    `document_type_id` INT NOT NULL COMMENT 'Fineract source column document_type_id',
    -- column_id: c2b880dc-d20f-4d10-9d82-48e5e15f7e30
    `document_key` VARCHAR(50) NOT NULL COMMENT 'Fineract source column document_key',
    -- column_id: 4a2fc23b-2d13-44bc-a08d-3fe5834cef1e
    `status` INT NOT NULL COMMENT 'Fineract source column status',
    -- column_id: b64c8ae8-dd7e-4669-9753-db7557cdc225
    `active` INT NULL COMMENT 'Fineract source column active',
    -- column_id: 02dd6b36-f829-4604-839a-8c7789cea4d6
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 63c098cd-9e6a-4f79-a580-08397db4e415
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 81ec56f3-5258-4dd0-a0be-dc12dcd42285
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a06e7e3e-5b3a-428c-aa9f-6e5070f72b0a
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 4c9ba44d-f5cd-4046-93b0-356528e8cff5
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: daf89bdb-442a-47d5-ad41-2b12c91836e6
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: b75a4cdf-7941-4d0e-8dd7-27493f70f935
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 0ff82ff9-d89c-48ed-a1d4-95ce7790567e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
