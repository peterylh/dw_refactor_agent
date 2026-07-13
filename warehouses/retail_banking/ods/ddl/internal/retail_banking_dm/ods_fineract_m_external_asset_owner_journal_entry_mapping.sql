-- ODS mirror of Apache Fineract m_external_asset_owner_journal_entry_mapping (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_journal_entry_mapping;
-- table_id: 7e9a66dd-6ed5-44e3-ba2f-ad67b6833193
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_journal_entry_mapping (
    -- column_id: 78b35e87-e5b4-4134-b356-5292da7441bf
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 33637688-3a51-4f13-b159-fea3d37287fa
    `journal_entry_id` BIGINT NOT NULL COMMENT 'Journal entry ID',
    -- column_id: ef7e47fb-2fca-4965-88d6-a91d7ff0a9c9
    `owner_id` BIGINT NULL COMMENT 'Owner',
    -- column_id: 8495b064-c8d7-4e73-9efb-f54d674035b2
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 5996bcb5-a483-4e24-a43a-858f5037b235
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 24945940-5348-49f6-abe9-1e749c436acc
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: afd46780-852e-44c4-bf47-c1e054df088b
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: d2764e56-135d-4c05-ab76-a8fa1deab30e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
