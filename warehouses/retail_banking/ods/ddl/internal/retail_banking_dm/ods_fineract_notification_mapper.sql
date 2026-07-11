-- ODS mirror of Apache Fineract notification_mapper (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_notification_mapper;
-- table_id: f516ff19-bb54-41c8-9eb3-7618bb8c7d3e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_notification_mapper (
    -- column_id: 9ac1a56b-d562-4a05-8c7a-5ffbcdd6331f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0325078d-b790-4e31-ba1b-d68f2b78f9e4
    `notification_id` BIGINT NULL COMMENT 'Fineract source column notification_id',
    -- column_id: fa68c89d-a0de-4c85-a7b0-b8f9de3ad4dc
    `user_id` BIGINT NULL COMMENT 'Fineract source column user_id',
    -- column_id: d3e1652f-f78b-4f07-aff1-4f46c478bd42
    `is_read` BOOLEAN NULL COMMENT 'Fineract source column is_read',
    -- column_id: 2b7ed814-2ebc-414f-a3ad-4bcec28fda85
    `created_at` DATETIME NULL COMMENT 'Fineract source column created_at',
    -- column_id: a4fdb3f5-c2d9-42d8-8fce-1c0f14773779
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
