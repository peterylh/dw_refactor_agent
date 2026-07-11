-- ODS mirror of Apache Fineract m_group_level (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_group_level;
-- table_id: 5135d3bb-6087-41f5-aa57-3efff1c08c00
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_group_level (
    -- column_id: 48681248-4cb6-4e1b-8bb5-1120c4e89e74
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c8ae6b2f-55d4-47d3-b0a7-05d95cc01a12
    `parent_id` INT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: 3500bd3b-5e2c-4e13-a004-8a8215086e1d
    `super_parent` BOOLEAN NOT NULL COMMENT 'Fineract source column super_parent',
    -- column_id: ef18ed76-7f58-4973-9dca-11f16f91d208
    `level_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column level_name',
    -- column_id: 7129ecde-9729-459d-b0ac-799905f92985
    `recursable` BOOLEAN NOT NULL COMMENT 'Fineract source column recursable',
    -- column_id: 7f262404-511e-4cb6-b9e2-004b33dcc9f1
    `can_have_clients` BOOLEAN NOT NULL COMMENT 'Fineract source column can_have_clients',
    -- column_id: 626d47e8-9794-4806-8264-65e4d008e495
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
