-- Reviewed aggregate from dwd_loan_ownership_transfer
DROP TABLE IF EXISTS retail_banking_dm.dws_loan_ownership_settlement_daily;
-- table_id: 619299a7-9346-4ff3-9318-df30850df5f0
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_loan_ownership_settlement_daily (
    -- column_id: 2cf1ea46-b0e8-497d-ba02-9e5e125d2c54
    `stat_date` DATE NOT NULL COMMENT 'settlement_event_date',
    -- column_id: f35e9020-8521-449d-b76f-fd72f92c1e80
    `owner_id` BIGINT NOT NULL COMMENT 'Fineract source column owner_id',
    -- column_id: 99392c1c-27d7-402d-be18-d013417704bd
    `loan_id` BIGINT NOT NULL COMMENT 'Loan ID',
    -- column_id: 976e3745-bef0-452a-a520-4b5d82cec74d
    `status` VARCHAR(50) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: 6cf1b1d5-b6a5-41a3-a73c-732777e7f84a
    `settlement_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 2d52c71e-25e9-4608-9e68-a1eae23d1abe
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `owner_id`, `loan_id`, `status`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
