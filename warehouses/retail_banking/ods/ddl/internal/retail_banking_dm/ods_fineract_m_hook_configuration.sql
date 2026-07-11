-- ODS mirror of Apache Fineract m_hook_configuration (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_hook_configuration;
-- table_id: a82e61b0-d7a8-4a18-8744-7cc816a4fcef
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_hook_configuration (
    -- column_id: 5a554ce7-2a39-4688-8ac8-a22571c45005
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9fc8aeb4-1f3c-4330-b5ef-fe9e03e3d545
    `hook_id` BIGINT NULL COMMENT 'Fineract source column hook_id',
    -- column_id: e2db2f32-143c-482f-be69-426677e9296a
    `field_type` VARCHAR(45) NOT NULL COMMENT 'Fineract source column field_type',
    -- column_id: 264f3542-ae2b-4c44-a5ab-e4ec0cb2d558
    `field_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column field_name',
    -- column_id: 7e894dca-f628-48f6-991f-18de7fd2aa3b
    `field_value` VARCHAR(100) NOT NULL COMMENT 'Fineract source column field_value',
    -- column_id: 9bf0b65a-f155-4c3b-ac74-79ecf29d631c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
