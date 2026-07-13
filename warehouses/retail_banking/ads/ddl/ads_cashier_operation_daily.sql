-- Reviewed application metrics derived from dws_cashier_transaction_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_cashier_operation_daily;
-- table_id: ae9c64ba-e59c-4532-8e70-a11a5e4f8751
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_cashier_operation_daily (
    -- column_id: 7ad72e48-d6ad-484e-8fcb-00144179beb5
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: ae369d17-cc9d-4c24-a815-c59eccebbcff
    `cashier_id` BIGINT NOT NULL COMMENT 'Fineract source column cashier_id',
    -- column_id: d472f16b-14d0-494f-b3f1-8dceee202276
    `currency_code` VARCHAR(3) NULL COMMENT 'Fineract source column currency_code',
    -- column_id: afbf0f0c-ea7e-4e49-90e7-3efa5c4be5c8
    `txn_type` SMALLINT NOT NULL COMMENT 'Fineract source column txn_type',
    -- column_id: d977d99a-4394-49e0-af52-18920ec8339e
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: 036e8aba-60ef-4552-8322-dee0bef8f04c
    `total_txn_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_txn_amount',
    -- column_id: 53305b67-38dc-4934-b76a-c7d97125ac4d
    `average_txn_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_txn_amount / nullif(record_count, 0)',
    -- column_id: 6ce3d0fc-8569-4f89-a209-791b8e80e18c
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `cashier_id`, `currency_code`, `txn_type`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
