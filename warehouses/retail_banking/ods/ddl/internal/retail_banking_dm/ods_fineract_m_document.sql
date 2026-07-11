-- ODS mirror of Apache Fineract m_document (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_document;
-- table_id: e5e3a92d-e989-4514-bed9-2a6687e7ddd4
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_document (
    -- column_id: 0aad2be9-bfba-4ec0-831c-178bf32fee30
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1bb65e24-b754-41d3-8411-1da33eb96ab8
    `parent_entity_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column parent_entity_type',
    -- column_id: 3829fdfe-e840-4302-aefd-e661cf4b9e02
    `parent_entity_id` INT NOT NULL COMMENT 'Fineract source column parent_entity_id',
    -- column_id: 06a0c6da-c7d9-4bf0-b2f9-d6320ff35550
    `name` VARCHAR(250) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: d174510c-8f8a-4a20-a9bb-db657e0c42f7
    `file_name` VARCHAR(250) NOT NULL COMMENT 'Fineract source column file_name',
    -- column_id: f6246458-fc96-4eee-87c5-56122a83f71f
    `size` INT NULL COMMENT 'Fineract source column size',
    -- column_id: 71d4c5d5-624b-4901-871e-d3b3673b226d
    `type` VARCHAR(500) NULL COMMENT 'Fineract source column type',
    -- column_id: 278380f4-0924-4c2c-8924-92c0cea150d0
    `description` VARCHAR(1000) NULL COMMENT 'Fineract source column description',
    -- column_id: 1c56b654-eac1-4fa2-bbed-4001494d7d3e
    `location` VARCHAR(500) NOT NULL COMMENT 'Fineract source column location',
    -- column_id: 07b008a6-6a9e-4db5-bfd2-b54873b6d2ba
    `storage_type_enum` SMALLINT NULL COMMENT 'Fineract source column storage_type_enum',
    -- column_id: 0f330092-8f17-4584-a13d-a0cb60984d84
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
