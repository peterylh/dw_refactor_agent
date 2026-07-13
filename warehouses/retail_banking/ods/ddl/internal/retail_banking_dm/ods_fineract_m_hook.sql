-- ODS mirror of Apache Fineract m_hook (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_hook;
-- table_id: 5a7357e4-7e4a-49ea-aef9-3c733bd11fbc
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_hook (
    -- column_id: ef4608a7-4758-4dfc-a296-d790ad954d95
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 3b402c0f-f625-4105-a10a-63e167cc8bcf
    `template_id` SMALLINT NOT NULL COMMENT 'Fineract source column template_id',
    -- column_id: 29c9df01-5873-4475-b6cc-23eb87edabd0
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 64859f9e-782e-43c3-8351-42ba9316affa
    `name` VARCHAR(45) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: a6b09c5e-9466-4ab2-8a53-4fc0534b2ab5
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 3886d1b6-9a48-4de6-bc74-2bba938fdec1
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: e690abea-00d7-4769-8c18-16609a5cdc7e
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 14c83b4e-5903-4360-8dfd-be5a09505977
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: b5f9de5d-9160-4a94-8ee0-5cb342b9ca91
    `ugd_template_id` BIGINT NULL COMMENT 'Fineract source column ugd_template_id',
    -- column_id: 2db1955a-96b2-4682-bb66-3454a7156610
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
