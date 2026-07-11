-- ODS mirror of Apache Fineract m_calendar_instance (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_calendar_instance;
-- table_id: c8160e9d-c38b-46e6-a40b-e478040d3458
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_calendar_instance (
    -- column_id: 7e134ada-1aae-4e98-bb4a-0652debb0f00
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 401748cc-450c-48ca-b981-d0d1ede1a5c7
    `calendar_id` BIGINT NOT NULL COMMENT 'Fineract source column calendar_id',
    -- column_id: d96cc315-b317-454c-b660-832c00dfcfa6
    `entity_id` BIGINT NOT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: 011b75f6-8350-4a0c-b119-5573e06f99bd
    `entity_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column entity_type_enum',
    -- column_id: e7887021-5440-4546-b66d-f404408d907d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
