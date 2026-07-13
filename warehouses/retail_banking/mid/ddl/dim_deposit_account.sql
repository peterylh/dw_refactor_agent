-- DIM generated from m_savings_account
DROP TABLE IF EXISTS retail_banking_dm.dim_deposit_account;
-- table_id: ceaf7e03-87fb-4d18-9e3c-da11ed1a4331
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_deposit_account (
    -- column_id: 81f0990e-2d33-4ed8-b6db-5f73b3c4fcdb
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 36991d21-f30f-474b-a204-ac2c3c9560ed
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 333f9ed0-0042-47a0-a121-99350c1f209e
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 788e8896-ef6c-443a-9622-ca68384b5f45
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 5394aaa2-db46-417a-934c-1bcd5eb2bf16
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 63cb783e-4aca-4c17-bda3-daa4b36d4f8f
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: ae501fc8-dfe1-40f6-9b02-4010f1eb599b
    `account_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column account_type_enum',
    -- column_id: 92492c7e-e583-4221-ad65-b216fbc6758d
    `deposit_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column deposit_type_enum',
    -- column_id: 9eadd4ee-cc33-454f-acb8-ed643cf5fb12
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 1636baeb-fd75-40db-8765-eaa7ba137c13
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
