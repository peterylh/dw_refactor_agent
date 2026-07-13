-- ODS mirror of Apache Fineract m_address (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_address;
-- table_id: 939eef75-370b-485e-bc00-e5cac0b0b7a5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_address (
    -- column_id: 6bb2c599-4e1c-4efa-ac79-b6ce8c92e5cd
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 200024af-5d95-4a96-ab4e-1af4115284d9
    `street` VARCHAR(100) NULL COMMENT 'Fineract source column street',
    -- column_id: f713ff69-79a8-472d-82d8-236493d0aa4e
    `address_line_1` VARCHAR(100) NULL COMMENT 'Fineract source column address_line_1',
    -- column_id: 41e82325-8316-47c1-a9af-88624a47a31b
    `address_line_2` VARCHAR(100) NULL COMMENT 'Fineract source column address_line_2',
    -- column_id: 3a441dbc-8457-497a-98cf-349798eb1e2c
    `address_line_3` VARCHAR(100) NULL COMMENT 'Fineract source column address_line_3',
    -- column_id: f219737d-9970-45b4-8d46-de41a6ec16dd
    `town_village` VARCHAR(100) NULL COMMENT 'Fineract source column town_village',
    -- column_id: 501fdcda-4e0e-4d4c-8c60-eadf8befe7aa
    `city` VARCHAR(100) NULL COMMENT 'Fineract source column city',
    -- column_id: 4b6e5e71-2b23-4baf-aaee-18b793f10d44
    `county_district` VARCHAR(100) NULL COMMENT 'Fineract source column county_district',
    -- column_id: bec55f81-a65b-41da-a6a2-a0e9d82d8b7a
    `state_province_id` INT NULL COMMENT 'Fineract source column state_province_id',
    -- column_id: ef4c2270-dbe3-4840-ad76-40d224f2c182
    `country_id` INT NULL COMMENT 'Fineract source column country_id',
    -- column_id: df6270c6-b8f9-41e2-80eb-d4b995eb996b
    `postal_code` VARCHAR(10) NULL COMMENT 'Fineract source column postal_code',
    -- column_id: fd1dcdbf-6fe4-43f5-a348-e82c6fd66c7c
    `latitude` DECIMAL(10,8) NULL COMMENT 'Fineract source column latitude',
    -- column_id: 26acb638-3815-46ab-8a1c-f0b53a91dced
    `longitude` DECIMAL(10,8) NULL COMMENT 'Fineract source column longitude',
    -- column_id: cb1d1700-ed81-47cc-9679-847a6059b294
    `created_by` VARCHAR(100) NULL COMMENT 'Fineract source column created_by',
    -- column_id: 56c4ef17-3e78-4985-aebc-7c7892a1de3b
    `created_on` DATE NULL COMMENT 'Fineract source column created_on',
    -- column_id: 7939bad7-dbbf-41c6-a6f1-9e8c72f98168
    `updated_by` VARCHAR(100) NULL COMMENT 'Fineract source column updated_by',
    -- column_id: 57a9713d-49a5-4725-a421-3b4309476d46
    `updated_on` DATE NULL COMMENT 'Fineract source column updated_on',
    -- column_id: 8d840cd6-bfaa-4889-9199-ea55e342e0de
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
