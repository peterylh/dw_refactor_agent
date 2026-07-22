-- Reviewed application metrics derived from dws_office_cash_transfer_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_branch_cash_transfer_daily;
-- table_id: 55c05d1c-dd0b-4119-9025-def322d1e9a2
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_branch_cash_transfer_daily (
    -- column_id: c6527d6a-f94f-4a39-9abb-434f08826be3
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 1149fef8-d628-42d7-b4ce-e9d53f6daf61
    `from_office_id` BIGINT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 518af673-8146-422c-bc92-17c0ac4f7204
    `to_office_id` BIGINT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: 0be4f805-c56f-4e84-a766-9dd53f15259f
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: a0a744ef-946b-44d8-a908-ed3ea2b6a44b
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: 84e69e70-dbbf-4002-974b-a3d59e034b01
    `total_transaction_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_transaction_amount',
    -- column_id: 7d41f519-9f68-4107-b0a5-c6f4248eb76c
    `average_transaction_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_transaction_amount / nullif(record_count, 0)',
    -- column_id: 44c2cb90-dbcf-42ad-9a87-21facdc86daa
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `from_office_id`, `to_office_id`, `currency_code`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
