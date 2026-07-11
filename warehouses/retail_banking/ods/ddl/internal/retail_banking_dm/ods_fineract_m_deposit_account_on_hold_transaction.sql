-- ODS mirror of Apache Fineract m_deposit_account_on_hold_transaction (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_deposit_account_on_hold_transaction;
-- table_id: 589a0506-6cc5-41c6-b9fa-ed9057bda429
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_deposit_account_on_hold_transaction (
    -- column_id: c688d7c8-f9fb-4c61-af18-43d3d531b15b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f8b33609-e502-48b0-b26a-c52ed638fe42
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 2116d21d-2d64-4237-8c3b-d262e5644aa6
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 7e3d00e6-bba7-4501-bd59-aa402e986436
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: bb52d854-bba5-4cc6-88b7-130dc241a725
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 9b4ecdc4-4c59-4a26-851b-9b6a988a383e
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 36731cba-d678-4128-9ee8-3582563dc651
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: c73912b9-031c-4120-9b08-0232654d6b40
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 3b5b11ae-8602-4185-bc66-1e0443efd899
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: fecdfe67-11c9-4cbf-9ff3-3b231d6507fc
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 481ffd4c-4f77-4291-b184-53484d9a6ded
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: caf9cd0f-edf1-497e-85e9-729b1f42d60c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
