SET allow_partition_column_nullable = true;

-- DWD generated from m_external_asset_owner_journal_entry_mapping
DROP TABLE IF EXISTS retail_banking_dm.bridge_asset_owner_gl_entry;
-- table_id: a0eca295-8995-4cc8-bfae-feba9d5e9de6
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_asset_owner_gl_entry (
    -- column_id: 602ace98-eec5-403e-b33d-3bfc8d0befa6
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 73a957f8-9be2-4e95-96b9-6e013357d0bc
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: bd8afcee-760e-47a9-b1fd-757914751c30
    `journal_entry_id` BIGINT NOT NULL COMMENT 'Journal entry ID',
    -- column_id: 6fbb69f7-b412-48df-809c-9b470a599200
    `owner_id` BIGINT NULL COMMENT 'Owner',
    -- column_id: b42d159b-9625-4ceb-aa1e-b4d55e7b615c
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 2500fc28-52b2-4f36-9d87-0925139304be
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 5ec3ad3f-0dfb-4901-a945-a5e59b5ca784
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: c4513522-477b-49d0-ab48-71f0d41cc909
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: ef361100-c83b-4241-9de8-1b63186f9c0f
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
