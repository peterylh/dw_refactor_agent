-- Reviewed aggregate from dwd_cashier_transaction
DROP TABLE IF EXISTS retail_banking_dm.dws_cashier_transaction_daily;
-- table_id: 2e2639a6-cc9d-4a74-942a-5ee1ce8b387e
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_cashier_transaction_daily (
    -- column_id: 7dc12230-795c-4957-8e4c-7b3c6fa3ba9c
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 2ae0c68d-11f6-4dd1-8f60-c36eb9d95560
    `cashier_id` BIGINT NOT NULL COMMENT 'Fineract source column cashier_id',
    -- column_id: f1c64638-4c98-4f4c-b78e-d33e46887a34
    `currency_code` VARCHAR(3) NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 91b26350-4b57-4c8d-b51b-d57da7d5f65a
    `txn_type` SMALLINT NOT NULL COMMENT 'Fineract source column txn_type',
    -- column_id: c5b9bd82-5eaa-4fc7-bb26-ef562b346762
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 81c89e38-92d7-4ffe-a3a8-e3d6a4e26986
    `total_txn_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(txn_amount)',
    -- column_id: 5a403704-d9e7-4bae-8a50-b3b8190d479a
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `cashier_id`, `currency_code`, `txn_type`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
