-- ODS mirror of Apache Fineract m_hook_schema (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_hook_schema;
-- table_id: 62995f14-585c-4863-9fb2-c88f94b8182d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_hook_schema (
    -- column_id: 5d595e0a-2fd7-4f52-bcdd-4a32b46a689e
    `id` SMALLINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 245e7759-9f98-4239-be5d-7662056dc178
    `hook_template_id` SMALLINT NOT NULL COMMENT 'Fineract source column hook_template_id',
    -- column_id: ba6f2795-c151-476e-a2b8-43e27255b369
    `field_type` VARCHAR(45) NOT NULL COMMENT 'Fineract source column field_type',
    -- column_id: feb91151-ea60-4438-a2e2-3e15f5547b0d
    `field_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column field_name',
    -- column_id: 08739fbc-0a3a-4fc6-9812-1f083246e303
    `placeholder` VARCHAR(100) NULL COMMENT 'Fineract source column placeholder',
    -- column_id: c7241db6-3ea0-46a5-8611-5720d35c7c98
    `optional` BOOLEAN NOT NULL COMMENT 'Fineract source column optional',
    -- column_id: 56daaa74-c9aa-418b-ba46-7fee59dbd8fc
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
