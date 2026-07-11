-- Reviewed aggregate from dwd_office_cash_transfer
DROP TABLE IF EXISTS retail_banking_dm.dws_office_cash_transfer_daily;
-- table_id: f7a86e05-98a9-4795-8cee-b743fc09a897
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_office_cash_transfer_daily (
    -- column_id: 6cd70901-b89e-4314-8a9c-014a13228d5a
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 15addb71-6159-4a71-b389-28d47f763d41
    `from_office_id` BIGINT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 650e42ec-2249-4286-bd69-cf7db4e759a8
    `to_office_id` BIGINT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: 3b93c35c-aa35-4bde-ba07-a4ac75fe1aea
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 045a53b5-da95-4df3-ae04-1f7c88982f69
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 9ea92dd0-576a-48de-8c39-ca5bc166f996
    `total_transaction_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(transaction_amount)',
    -- column_id: 8a0bed3b-ac04-4120-b5f1-9ec0c78f1a19
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `from_office_id`, `to_office_id`, `currency_code`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
