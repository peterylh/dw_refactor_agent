-- ODS mirror of Apache Fineract m_payment_detail (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_payment_detail;
-- table_id: 711bec84-a2ce-4a1f-8fad-fa953d50c529
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_payment_detail (
    -- column_id: 9f6ef938-31a9-4a1f-a2e5-4e851456cd2a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5a4d7d7d-d6b2-43df-9513-9368854af3e3
    `payment_type_id` INT NULL COMMENT 'Fineract source column payment_type_id',
    -- column_id: 482d543a-f230-4bf7-b38c-5d7663dffaec
    `account_number` VARCHAR(100) NULL COMMENT 'Fineract source column account_number',
    -- column_id: d6004866-43c2-49f2-a67b-a45687daff81
    `check_number` VARCHAR(100) NULL COMMENT 'Fineract source column check_number',
    -- column_id: dc67c372-9a52-4fab-b3f8-b04fa527bd25
    `receipt_number` VARCHAR(100) NULL COMMENT 'Fineract source column receipt_number',
    -- column_id: 8ee2e858-a6c6-4026-bb26-99e6b244e10d
    `bank_number` VARCHAR(100) NULL COMMENT 'Fineract source column bank_number',
    -- column_id: 9c9036a2-9594-47a2-bf6e-030906612c75
    `routing_code` VARCHAR(100) NULL COMMENT 'Fineract source column routing_code',
    -- column_id: 686e02ca-0c3d-4958-919f-c62d030d7a3a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
