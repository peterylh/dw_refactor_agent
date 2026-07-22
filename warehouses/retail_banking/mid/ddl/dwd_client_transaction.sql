SET allow_partition_column_nullable = true;

-- DWD generated from m_client_transaction
DROP TABLE IF EXISTS retail_banking_dm.dwd_client_transaction;
-- table_id: 30d627bd-6f8d-4bb0-9699-e9a29127a29c
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_client_transaction (
    -- column_id: cc5fc597-19db-4eac-915e-3b938f15fbe0
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 8a6bbabb-e42e-42e4-9e4f-0c1815b65ae7
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: a0622403-5d04-4d18-b7cd-f308a3ea0423
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 7333dc36-64e5-4bf3-babf-2775a344ade0
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 5cd2dd86-5e8a-4ebe-8117-affdbb03b02f
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 4a907f4c-fc4c-4916-a2aa-ec7a4ee46f72
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: 15a5080a-e74c-4fad-9fed-b8de14cc3518
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 56c5b82a-91c4-4ae2-98cb-7caf04fbb43e
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: eedeecb2-0d81-4152-96ce-9a6ca3a4b550
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: f6b9cd33-4c9d-402e-b11b-ea47527f0f04
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 3b68d515-faf0-4387-b307-51526c0944f4
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: e7a36e31-6be4-4cd5-b08c-b82af118dae0
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 736a1d21-b605-4a91-b8cb-5ce5833c970b
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 3b22d000-16dd-489c-88fd-ee3012a8913b
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 63c1ce4c-2cce-454e-ba70-e2af4163b125
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 20eddcba-5636-4976-ae68-3e449f55a77a
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: a479db1f-0ebd-4548-81ff-dfef25af399e
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: c6c9bef8-c73e-4022-bbec-c1f4c237ce0b
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
