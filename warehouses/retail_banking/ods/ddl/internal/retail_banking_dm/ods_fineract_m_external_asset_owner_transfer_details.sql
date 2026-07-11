-- ODS mirror of Apache Fineract m_external_asset_owner_transfer_details (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_details;
-- table_id: 688ad3f6-9800-45e6-91c5-a557dab16c0e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_details (
    -- column_id: 1ef94473-6160-4475-96a7-b4c9aeed884e
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: ec5d7bf9-4397-4dd6-ab2a-d4b94824bc46
    `asset_owner_transfer_id` BIGINT NOT NULL COMMENT 'Id of asset owner transfer',
    -- column_id: fa607dd4-2cab-46fe-9ad4-62cc138632c3
    `total_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_outstanding_derived',
    -- column_id: 66bd95b9-3aee-4429-9ac8-445947066697
    `principal_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_outstanding_derived',
    -- column_id: 6ae2db25-ee54-48f1-b318-ede67b9cc22d
    `interest_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_outstanding_derived',
    -- column_id: b5cc5d1c-7d78-4d87-b28b-1ddafca5d185
    `fee_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_outstanding_derived',
    -- column_id: b7d72425-8f34-4718-afd7-df32d79710c8
    `penalty_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_outstanding_derived',
    -- column_id: d875ca79-361e-49f0-9e26-7362a1ac418b
    `total_overpaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_overpaid_derived',
    -- column_id: 280cbaa0-bd37-4325-a35a-4ac4e9700e44
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 3cd617bf-46d2-4f1a-9120-514229174757
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 4acf3c28-9baf-41d1-80f2-a793655a3aa0
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 96a5002f-4147-4fd4-9e10-d0bbceb21322
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 3af59061-4819-4256-9936-33a62875bfa6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
