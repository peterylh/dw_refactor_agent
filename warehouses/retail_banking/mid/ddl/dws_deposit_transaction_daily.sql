-- Reviewed aggregate from dwd_deposit_transaction
DROP TABLE IF EXISTS retail_banking_dm.dws_deposit_transaction_daily;
-- table_id: 8d6f8d9d-d951-4aa1-8388-4d88fa38e428
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_deposit_transaction_daily (
    -- column_id: a746508f-e2ca-48cc-91d7-fbee1bae3afb
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: afdcdafd-5649-46e3-9d2b-873335a3f262
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 41a8e088-35a4-4cc0-ad42-18cf4286cd6e
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 4a5394fe-072c-482d-a4d9-ad8b78c9a8d4
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 192af4f7-7b24-4d73-bc1f-a248e910ed61
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 7a565e8b-10b0-425d-8e0b-5e737c64e6d1
    `total_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: ba6368f5-a728-4c3c-ba61-eb6bde1f5341
    `total_overdraft_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(overdraft_amount_derived)',
    -- column_id: bb80bf21-e2ce-4de3-868a-df9a17a638b2
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `savings_account_id`, `transaction_type_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
