-- ODS mirror of Apache Fineract m_external_asset_owner_transfer_journal_entry_mapping (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_journal_entry_mapping;
-- table_id: 989d2ba3-ff33-4e47-8f22-88a662b08524
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_journal_entry_mapping (
    -- column_id: fa31dad0-a58e-47f0-a2cc-b511ffbf9d50
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 8fcf0679-31a3-4cad-9531-446c13ee5819
    `journal_entry_id` BIGINT NOT NULL COMMENT 'Journal entry ID',
    -- column_id: 1504a67a-caf5-43b3-ab99-17d3ccbc493a
    `owner_transfer_id` BIGINT NULL COMMENT 'Owner transfer',
    -- column_id: 69a84c30-dc11-4ef4-a27d-4fb6df6f2ac5
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: d0147e55-19c8-443c-9487-cb67e819bff8
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 0797aa71-0602-4303-ad78-71171838558d
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: f6607e8a-c049-4b0a-aeef-b968785b8eb3
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 7d84699c-21e5-48ab-86ad-9d86d1ab8274
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
