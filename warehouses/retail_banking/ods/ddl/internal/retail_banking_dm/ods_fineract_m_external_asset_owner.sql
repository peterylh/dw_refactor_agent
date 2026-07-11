-- ODS mirror of Apache Fineract m_external_asset_owner (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner;
-- table_id: 71111856-52dd-4348-b161-ca3741be311c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner (
    -- column_id: 186d5e0d-a0e6-4e95-a659-1c34c14298be
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 709cb66d-c5ce-4739-98a0-80d6a1fb1d84
    `external_id` VARCHAR(100) NOT NULL COMMENT 'External id of asset owner',
    -- column_id: e2405ad6-2e78-4863-9675-a7f16f04a974
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: bda94bdb-1cf2-4f03-8446-2b581b34b2ae
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: da3da0af-1264-4db3-b531-93fe43bbdc19
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 4ca58290-84cf-4797-9fa6-ff6b9c35dd12
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 2e850959-a5b0-40dc-93ff-ea8e4ce99d7f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
