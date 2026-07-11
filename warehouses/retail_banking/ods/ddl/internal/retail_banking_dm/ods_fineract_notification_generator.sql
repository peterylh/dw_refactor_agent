-- ODS mirror of Apache Fineract notification_generator (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_notification_generator;
-- table_id: 71f09373-e8ee-4647-976a-726fed345f30
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_notification_generator (
    -- column_id: a7aaae32-5ebc-41e4-83cd-4b4e5a923d13
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 3c98faa3-ed72-4a33-8e8d-06e2685f7bd4
    `object_type` STRING NULL COMMENT 'Fineract source column object_type',
    -- column_id: 1cee1248-05b1-475d-b742-314d78ff3f7d
    `object_identifier` BIGINT NULL COMMENT 'Fineract source column object_identifier',
    -- column_id: bd8dc4d6-167a-487a-95fd-940ad105ad12
    `action` STRING NULL COMMENT 'Fineract source column action',
    -- column_id: 81c5cb72-ce31-4b18-995f-942bcdc72eea
    `actor` BIGINT NULL COMMENT 'Fineract source column actor',
    -- column_id: eeed669e-59ef-4338-96b2-75507d326e63
    `is_system_generated` BOOLEAN NULL COMMENT 'Fineract source column is_system_generated',
    -- column_id: fe0501f1-3e27-4816-85a9-2c9311840a99
    `notification_content` STRING NULL COMMENT 'Fineract source column notification_content',
    -- column_id: a6db8f22-019a-404b-bd44-3c957d24ee8f
    `created_at` DATETIME NULL COMMENT 'Fineract source column created_at',
    -- column_id: f0002231-a2c2-4bdd-8279-cbbe58431757
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
