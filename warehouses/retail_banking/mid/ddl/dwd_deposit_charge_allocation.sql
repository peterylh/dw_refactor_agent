-- DWD generated from m_savings_account_charge_paid_by
DROP TABLE IF EXISTS retail_banking_dm.dwd_deposit_charge_allocation;
-- table_id: 0084f2b0-c26a-45d4-a29d-0d70872ce77e
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_deposit_charge_allocation (
    -- column_id: 644e5119-2850-4be8-9027-1c15cca91174
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f3efec0f-5ada-4a07-894d-780bf4a4725b
    `savings_account_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_transaction_id',
    -- column_id: 5e041526-3ddb-4609-99e9-d2555fb383fd
    `savings_account_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_charge_id',
    -- column_id: cdff5a63-8d82-4684-a2f7-74a13421d42d
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 25a690d5-0fe8-4260-af2d-16942957af10
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: f0e4d36c-96f3-45f4-a7b0-d1149f500017
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
