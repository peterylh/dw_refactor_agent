-- ODS mirror of Apache Fineract m_field_configuration (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_field_configuration;
-- table_id: 95b27404-d281-4bd0-b18d-28d2c1970463
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_field_configuration (
    -- column_id: a557198b-b98f-4883-a47a-d9818fffb071
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6fca9853-4843-4ef9-8e74-aab224a70605
    `entity` VARCHAR(100) NOT NULL COMMENT 'Fineract source column entity',
    -- column_id: 86e6aa3b-7559-4bc1-b900-27ba80308a89
    `subentity` VARCHAR(100) NOT NULL COMMENT 'Fineract source column subentity',
    -- column_id: 3d8b1b95-e939-431c-af18-38a00a4ae015
    `field` VARCHAR(100) NOT NULL COMMENT 'Fineract source column field',
    -- column_id: f895d92d-827a-44d1-b66a-0da45616624b
    `is_enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column is_enabled',
    -- column_id: 29959fdd-e2fe-46fe-8068-d62b1f77d13c
    `is_mandatory` BOOLEAN NOT NULL COMMENT 'Fineract source column is_mandatory',
    -- column_id: e069b1b1-da1e-4548-9d9e-fc70714ebd11
    `validation_regex` VARCHAR(50) NULL COMMENT 'Fineract source column validation_regex',
    -- column_id: e620fad8-3fbf-4a8e-aa0a-c1df61abe47b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
