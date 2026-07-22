SET allow_partition_column_nullable = true;

-- DWD generated from m_cashier_transactions
DROP TABLE IF EXISTS retail_banking_dm.dwd_cashier_transaction;
-- table_id: fc93f5f8-8dc3-4890-b678-703862756dbe
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_cashier_transaction (
    -- column_id: 77c516c2-b8e6-403b-acb6-cbb79219ea4c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c328dc62-57ee-447c-bcf0-d1e3b1993fb9
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 816a2c1e-6d42-4a7d-8037-e87fd8b65bc6
    `cashier_id` BIGINT NOT NULL COMMENT 'Fineract source column cashier_id',
    -- column_id: f3909adc-aca6-48a8-9ca5-e478ffa96e91
    `txn_type` SMALLINT NOT NULL COMMENT 'Fineract source column txn_type',
    -- column_id: 3918afef-f3d6-4ef2-93a3-56231e9e051d
    `txn_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column txn_amount',
    -- column_id: 2b54337e-ab83-4b99-b2d2-0551f02e1f14
    `txn_date` DATE NOT NULL COMMENT 'Fineract source column txn_date',
    -- column_id: 2dd56f71-0b53-4591-b25f-32d3949f8ff5
    `created_date` DATETIME NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: 62f080f5-ed43-4a47-b1ce-fc97e40e843b
    `entity_type` VARCHAR(50) NULL COMMENT 'Fineract source column entity_type',
    -- column_id: 3257f07b-3d01-46e4-8860-130903d193a6
    `entity_id` BIGINT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: 02faaa1d-fc45-40a9-af2a-bf8002c744da
    `txn_note` VARCHAR(200) NULL COMMENT 'Fineract source column txn_note',
    -- column_id: 59d4e2c3-45b2-4fb1-ae43-27d02cdddedc
    `currency_code` VARCHAR(3) NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 56d2c95e-210b-4cf8-80f1-860539feddd6
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
