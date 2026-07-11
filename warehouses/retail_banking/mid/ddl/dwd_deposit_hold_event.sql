-- DWD generated from m_deposit_account_on_hold_transaction
DROP TABLE IF EXISTS retail_banking_dm.dwd_deposit_hold_event;
-- table_id: 63bb4b1f-908d-47a7-b961-2fcdfd498444
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_deposit_hold_event (
    -- column_id: d0b30159-0db1-4d87-9165-6cd3245ec53a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: de0cc3f2-41e6-452c-b367-4a529e3d88a6
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 7a092353-ec94-4dfd-b54a-6f68af6bb72f
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 8ab63432-bc25-421f-aa52-9d2286b78065
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: e34b93ca-a7fe-48ce-b423-a5ae4e47a7eb
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 02d542a0-36da-4f79-af52-23da6e46a68f
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 2e9d6126-0144-4ce3-8e05-fdfc174d5fdc
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 264896d6-978e-44d7-80a0-ef75710ae7df
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 7c3f2bd3-e2ad-43f3-afbc-25cd5068434b
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: b8f16187-b9a1-4e2b-a455-d9e7be36d0a3
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: cb857887-93c8-4c0f-903e-d1e1bb84537c
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 25c62e4e-9255-4114-93e9-0d9e2c7af249
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 21de7df4-8b7c-44f4-a373-40333a150958
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
