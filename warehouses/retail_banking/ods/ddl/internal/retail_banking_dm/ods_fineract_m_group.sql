-- ODS mirror of Apache Fineract m_group (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_group;
-- table_id: f7565769-94bf-4478-b093-f91de41e35c1
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_group (
    -- column_id: 0fb830be-aac3-42f7-aaca-15006a779f4a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: feafe0b3-4571-4c6d-9f37-3bbe15c76b8e
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: b13b19d4-1ac1-426c-b154-526a36f229e4
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 6159afb1-c5a4-4d50-ac6f-9fd68414257a
    `activation_date` DATE NULL COMMENT 'Fineract source column activation_date',
    -- column_id: 98b429d9-7a35-46fa-b1b0-47b36f353074
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 63b4e84c-5c9e-48f1-9f93-fdf2320ce464
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: db2ca09b-d8cc-4d96-94c7-0c02a86cc071
    `parent_id` BIGINT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: d34f5ecf-4942-4391-a7c2-ddf1f0e25854
    `level_id` INT NOT NULL COMMENT 'Fineract source column level_id',
    -- column_id: 0f489b3a-dc99-40f7-b1fd-83d5b5efa7c8
    `display_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column display_name',
    -- column_id: ee969df0-1852-4c25-bf1a-93d8bc096789
    `hierarchy` VARCHAR(100) NULL COMMENT 'Fineract source column hierarchy',
    -- column_id: f207ff34-d47d-43c2-b3ed-4ddfdbf273cb
    `closure_reason_cv_id` INT NULL COMMENT 'Fineract source column closure_reason_cv_id',
    -- column_id: 22dc05ad-84d5-48e0-9584-441a329f4bb8
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 02b5a094-36e9-4d87-af04-f2807fde07df
    `activatedon_userid` BIGINT NULL COMMENT 'Fineract source column activatedon_userid',
    -- column_id: 4b177869-6f02-4090-b9d3-73ab5245543b
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 4e79ecd2-144f-4deb-a689-8b709eb8aa06
    `submittedon_userid` BIGINT NULL COMMENT 'Fineract source column submittedon_userid',
    -- column_id: 0efd954f-f1c3-4ee0-8a94-22fa0592c371
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 703d4626-22cc-444b-adc4-8483e22c771f
    `account_no` VARCHAR(20) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 8950becd-8a3d-4189-a376-c9356bfed12f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
