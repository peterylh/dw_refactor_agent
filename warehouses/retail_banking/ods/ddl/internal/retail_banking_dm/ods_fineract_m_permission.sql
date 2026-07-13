-- ODS mirror of Apache Fineract m_permission (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_permission;
-- table_id: 48e116d6-80c4-4df9-a21b-1884eeead511
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_permission (
    -- column_id: dffce11f-64df-4497-96de-436c47f17c4a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 70e16c50-a5e4-4527-8c64-1a0415d067b0
    `grouping` VARCHAR(45) NULL COMMENT 'Fineract source column grouping',
    -- column_id: f0b9f084-9bc6-4224-8ccb-1399919419a4
    `code` VARCHAR(100) NOT NULL COMMENT 'Fineract source column code',
    -- column_id: 1d84cad0-9478-490b-954d-1a9ead3790dc
    `entity_name` VARCHAR(100) NULL COMMENT 'Fineract source column entity_name',
    -- column_id: 1c63040c-ef53-463d-b064-96089c0b32da
    `action_name` VARCHAR(100) NULL COMMENT 'Fineract source column action_name',
    -- column_id: ead1b558-baf9-4b90-a5e5-ae1311175e12
    `can_maker_checker` BOOLEAN NOT NULL COMMENT 'Fineract source column can_maker_checker',
    -- column_id: c67d4446-657e-4189-ab8e-5303f0f66c67
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
