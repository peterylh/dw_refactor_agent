-- ODS mirror of Apache Fineract m_entity_to_entity_mapping (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_entity_to_entity_mapping;
-- table_id: 1ec1d46c-eb24-4940-8785-85ace21106e0
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_entity_to_entity_mapping (
    -- column_id: c7215644-8166-4c64-9b65-13903710c05e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ba3b3d0a-3983-4b01-87c6-8a79b1b27578
    `rel_id` BIGINT NOT NULL COMMENT 'Fineract source column rel_id',
    -- column_id: 307d98a1-87b0-47d4-a34a-6895c87424ec
    `from_id` BIGINT NOT NULL COMMENT 'Fineract source column from_id',
    -- column_id: 4c95e21f-3602-49b7-9201-d221cb54b816
    `to_id` BIGINT NOT NULL COMMENT 'Fineract source column to_id',
    -- column_id: 8110f33e-72d6-4f45-8640-0f7d67870fc1
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: 859ebaa5-31b2-4a1f-ba82-633397193819
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: a30bed12-fba0-4dc9-a634-c9ad5c87ee15
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
