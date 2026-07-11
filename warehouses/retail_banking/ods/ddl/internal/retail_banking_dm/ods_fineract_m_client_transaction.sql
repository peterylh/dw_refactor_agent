-- ODS mirror of Apache Fineract m_client_transaction (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_transaction;
-- table_id: a2d1190a-23da-4a10-b5d0-9ad490c4e139
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_transaction (
    -- column_id: dd3c2856-f161-4df4-8015-a267ac085123
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b8e3f523-6198-46c0-8702-203411f26083
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 14200946-a911-44cc-958c-9fccb092d913
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 6b4fe20b-6c01-43be-b78a-670fdde2d0b4
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 991c2c3e-ccb5-4dcd-ad1a-ff7eef975b86
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: a443a4f6-7f21-4f80-abf0-e8152e0578dc
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: d4d634d9-12bb-4d2b-927d-d57e5d978ad4
    `external_id` VARCHAR(50) NULL COMMENT 'Fineract source column external_id',
    -- column_id: cbc8883a-9b8e-4cea-8084-2306ad5f0853
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: dd62dbe0-7ff4-4c33-8fee-36d1e2bf66ef
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: a2616d4b-e97c-4fe2-8b46-7fc949f40b9a
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 7f0d90e2-0387-4d6b-9c5a-9c8b4db274df
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: ac62ec22-753a-4465-886b-7303d49f6c1f
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 379f1b9d-2c54-470f-af60-5912d8bb637f
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 0092e443-3c2b-4b8b-af4e-819eefac2c96
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a8d4e4d6-6c26-472b-94c1-da796bb15590
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: bc5c452e-c55e-48ff-9d05-7d8f8cc81c05
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 417183be-e85a-437d-984f-a3639f956e7c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
