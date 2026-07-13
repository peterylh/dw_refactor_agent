-- ODS mirror of Apache Fineract m_entity_to_entity_access (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_entity_to_entity_access;
-- table_id: 7e00ff7f-25a4-4ba7-b903-ec4e2c7bcfc3
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_entity_to_entity_access (
    -- column_id: 8409013b-119e-4317-af5d-bf418131ee63
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: dbc58e2f-43dc-4262-9a8f-60e95d07104f
    `entity_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column entity_type',
    -- column_id: a553c9d5-3c6f-4742-8e45-f7ce8558092c
    `entity_id` BIGINT NOT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: bdebda42-4be2-4309-b49b-bd1366402d9d
    `access_type_code_value_id` INT NOT NULL COMMENT 'Fineract source column access_type_code_value_id',
    -- column_id: d4d0c3db-827c-44de-ab77-3cb85e143661
    `second_entity_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column second_entity_type',
    -- column_id: 39a47144-7031-45cb-9f4e-38b1f984070d
    `second_entity_id` BIGINT NOT NULL COMMENT 'Fineract source column second_entity_id',
    -- column_id: 5461a9c6-39d0-44ad-b6f7-7f18bb4eafe9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
