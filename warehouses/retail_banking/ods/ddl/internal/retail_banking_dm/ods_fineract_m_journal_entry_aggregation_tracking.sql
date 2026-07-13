-- ODS mirror of Apache Fineract m_journal_entry_aggregation_tracking (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_journal_entry_aggregation_tracking;
-- table_id: f71e8f49-de49-4513-92dd-06d1b4a885ab
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_journal_entry_aggregation_tracking (
    -- column_id: bb13c1e0-3632-4b7f-ba40-c1c3dba062d6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9fae9c80-9316-4d1f-b780-5a467be3112b
    `aggregated_on_date_from` DATE NOT NULL COMMENT 'Fineract source column aggregated_on_date_from',
    -- column_id: d13c4d56-fb5b-45b4-a630-b6aac3564a49
    `aggregated_on_date_to` DATE NOT NULL COMMENT 'Fineract source column aggregated_on_date_to',
    -- column_id: a3e104fa-8e08-4b2e-8cba-d04c6c671e88
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 13fdce58-8709-4c9d-99b3-2ec6018ea16e
    `job_execution_id` BIGINT NOT NULL COMMENT 'Fineract source column job_execution_id',
    -- column_id: 37d9b25d-c186-43ed-bcc0-95c9bf000aa0
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 4cdc4427-786c-4b13-bff5-36e34f6b98cb
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: b77614c3-b7f5-48ff-908e-126301a0f5b7
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: b8aead02-3ba8-4972-84af-5a0c5b201d67
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 94852bd4-5cb0-4a7f-8dcd-0630c0c7a2b1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
