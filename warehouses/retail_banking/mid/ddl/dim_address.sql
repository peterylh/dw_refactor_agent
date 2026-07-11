-- DIM generated from m_address
DROP TABLE IF EXISTS retail_banking_dm.dim_address;
-- table_id: 41f37a33-f066-4bbb-becd-ac251446726e
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_address (
    -- column_id: 8f33d29e-1f14-4de3-a37c-8e66c73bbe4a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 12ba7dd3-5799-448e-894e-ae7f6cb857a3
    `street` VARCHAR(256) NULL COMMENT 'Fineract source column street',
    -- column_id: bb0da6ae-9c05-431d-855e-542154a5f3cf
    `address_line_1` VARCHAR(256) NULL COMMENT 'Fineract source column address_line_1',
    -- column_id: d1465e12-2cc1-4c28-9d4c-670fcbc8f673
    `address_line_2` VARCHAR(256) NULL COMMENT 'Fineract source column address_line_2',
    -- column_id: 60d15565-c5f4-4dba-8022-6217a5317c44
    `address_line_3` VARCHAR(256) NULL COMMENT 'Fineract source column address_line_3',
    -- column_id: 0a751963-270f-4568-abc7-5aedddd1420c
    `town_village` VARCHAR(256) NULL COMMENT 'Fineract source column town_village',
    -- column_id: 6c141d2b-1020-4704-b232-0e3522bbdc34
    `city` VARCHAR(256) NULL COMMENT 'Fineract source column city',
    -- column_id: e48de0f6-3092-4eb7-93e5-5bd604b2e765
    `county_district` VARCHAR(256) NULL COMMENT 'Fineract source column county_district',
    -- column_id: c1b1b528-5a08-494d-8302-d53e54c731d7
    `state_province_id` INT NULL COMMENT 'Fineract source column state_province_id',
    -- column_id: 81aad8f8-8331-4336-a5a6-d1a5f1f43781
    `country_id` INT NULL COMMENT 'Fineract source column country_id',
    -- column_id: ad05c005-5eaf-486a-aac3-f1eb8bf20bd4
    `postal_code` VARCHAR(256) NULL COMMENT 'Fineract source column postal_code',
    -- column_id: e7f99e6b-0edc-494d-8538-2a51ac14da15
    `latitude` VARCHAR(256) NULL COMMENT 'Fineract source column latitude',
    -- column_id: 3666172f-a835-4dcd-bad9-e968c4b25d07
    `longitude` VARCHAR(256) NULL COMMENT 'Fineract source column longitude',
    -- column_id: c8e66910-e85a-4c5c-813d-c64bef30216f
    `created_by` VARCHAR(100) NULL COMMENT 'Fineract source column created_by',
    -- column_id: 526f3291-22aa-4a10-900d-47f8f19fad22
    `created_on` DATE NULL COMMENT 'Fineract source column created_on',
    -- column_id: ba56f0ad-dc76-402e-a63b-22234a0e2ddc
    `updated_by` VARCHAR(100) NULL COMMENT 'Fineract source column updated_by',
    -- column_id: 46ccd469-07dc-4eb4-9d1a-4a7bcd54e309
    `updated_on` DATE NULL COMMENT 'Fineract source column updated_on',
    -- column_id: 7efb71a4-91f3-4b2c-ae48-b2aa05b37d94
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
