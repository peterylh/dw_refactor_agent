-- ODS mirror of Apache Fineract m_code_value (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_code_value;
-- table_id: 0685463e-43fe-4795-be51-1497f19c5536
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_code_value (
    -- column_id: 3b11fa0d-4d02-473d-9592-5eb9459afa02
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9c25b59b-ebcd-47f2-b472-a6b246fcf3fc
    `code_id` INT NOT NULL COMMENT 'Fineract source column code_id',
    -- column_id: 4dc52977-d4aa-495b-88c4-6883bda12a07
    `code_value` VARCHAR(100) NULL COMMENT 'Fineract source column code_value',
    -- column_id: 9e4a85e9-d7fb-4e56-92c6-12a335ff4020
    `code_description` VARCHAR(500) NULL COMMENT 'Fineract source column code_description',
    -- column_id: 062a0f19-07ab-403c-8814-f870e90bb2b2
    `order_position` INT NOT NULL COMMENT 'Fineract source column order_position',
    -- column_id: 0e650cd5-c748-4fac-b3de-3412f532f7d1
    `code_score` INT NULL COMMENT 'Fineract source column code_score',
    -- column_id: 1b8e204b-79f8-4752-a31c-0e9a3aa64352
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 331d7678-ddbf-4c6e-81be-219c28e4ca14
    `is_mandatory` BOOLEAN NOT NULL COMMENT 'Fineract source column is_mandatory',
    -- column_id: 48a80a1b-ecb7-457c-96ac-aea01264cdb2
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
