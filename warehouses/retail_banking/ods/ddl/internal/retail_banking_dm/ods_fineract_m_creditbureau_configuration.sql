-- ODS mirror of Apache Fineract m_creditbureau_configuration (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_creditbureau_configuration;
-- table_id: fbe87e13-c738-4b16-9f9c-8c725f217d69
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_creditbureau_configuration (
    -- column_id: ef5b43a0-1125-4adc-b90c-b6169fec8427
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bfd1cf8d-9469-47ba-89ad-aa9337ab7c53
    `configkey` VARCHAR(50) NULL COMMENT 'Fineract source column configkey',
    -- column_id: 161f8929-6577-4ea0-8ef1-2edcf7fb1078
    `value` STRING NULL COMMENT 'Fineract source column value',
    -- column_id: 01b27d81-ba67-47c7-89a5-fb637040d813
    `organisation_creditbureau_id` BIGINT NULL COMMENT 'Fineract source column organisation_creditbureau_id',
    -- column_id: f23ad0b1-068e-43ca-80ec-5371871f40e3
    `description` VARCHAR(50) NULL COMMENT 'Fineract source column description',
    -- column_id: 7e66c58a-265d-4a3e-8b6d-d95c1addb68c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
