-- ODS mirror of Apache Fineract m_cashier_transactions (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_cashier_transactions;
-- table_id: a4a9e376-7ba1-4b50-8c17-6e184e026ec8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_cashier_transactions (
    -- column_id: ec30b7d4-b339-41d8-8163-c48e3c5a48a0
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 78783448-eee1-4f3e-a1e2-cbbea5ce5ba6
    `cashier_id` BIGINT NOT NULL COMMENT 'Fineract source column cashier_id',
    -- column_id: 00bb6023-a825-4fe3-8e0a-181478db3755
    `txn_type` SMALLINT NOT NULL COMMENT 'Fineract source column txn_type',
    -- column_id: 9defdd69-472f-4b7f-be22-00fc755814b9
    `txn_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column txn_amount',
    -- column_id: ad30a3fe-e522-4aaa-997e-dedd6f7137bf
    `txn_date` DATE NOT NULL COMMENT 'Fineract source column txn_date',
    -- column_id: e7b94fdf-03a3-4cc8-a7f1-a144973b35db
    `created_date` DATETIME NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: 72537cfb-d70b-4053-9087-063ca67afc05
    `entity_type` VARCHAR(50) NULL COMMENT 'Fineract source column entity_type',
    -- column_id: 28c95277-e322-48b7-b240-8879b6b5963a
    `entity_id` BIGINT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: 86eb1d35-5410-46ca-9ba1-20008f9b6d22
    `txn_note` VARCHAR(200) NULL COMMENT 'Fineract source column txn_note',
    -- column_id: 3c2153b3-d930-4832-941b-78f8974f1f34
    `currency_code` VARCHAR(3) NULL COMMENT 'Fineract source column currency_code',
    -- column_id: e335dd3b-9414-49c9-9bd0-e954db0581eb
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
