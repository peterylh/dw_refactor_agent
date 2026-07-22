-- Reviewed aggregate from dwd_wc_loan_transaction
DROP TABLE IF EXISTS retail_banking_dm.dws_wc_loan_transaction_daily;
-- table_id: b86a6ba0-62cd-4f91-8fcb-c10eb3b99e0a
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_wc_loan_transaction_daily (
    -- column_id: 922b58b5-0fde-4e05-ba35-d7bf23bcbbb7
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: aeca3ecb-208c-4986-a4fa-e7b5bdc18cc6
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: d6e8faab-d0e5-421d-92f7-7acac9c16ad4
    `transaction_type_id` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_id',
    -- column_id: 958a34c1-8ce5-47b9-8d3c-8b3fa2137ec6
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 54e4707c-2f51-4187-8367-0eb15cbdee55
    `total_transaction_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(transaction_amount)',
    -- column_id: a806b558-afba-4df8-abd6-7cca4f3d6ac4
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `wc_loan_id`, `transaction_type_id`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
