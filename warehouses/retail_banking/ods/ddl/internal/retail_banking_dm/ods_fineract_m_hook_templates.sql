-- ODS mirror of Apache Fineract m_hook_templates (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_hook_templates;
-- table_id: 4da85f50-e21a-4b48-8473-f2be653189ba
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_hook_templates (
    -- column_id: 6c9e2469-7458-4df9-91ed-b7089ae54297
    `id` SMALLINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: fed6a74b-17da-4975-a9f1-19d475966660
    `name` VARCHAR(45) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: dd6f8122-dab3-4e03-8d59-e9ccebf7cffb
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
