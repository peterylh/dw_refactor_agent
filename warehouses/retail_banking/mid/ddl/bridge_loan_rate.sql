-- DIM generated from m_loan_rate
DROP TABLE IF EXISTS retail_banking_dm.bridge_loan_rate;
-- table_id: 3b297f0a-6f04-43ff-844b-f7cdec302bc0
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_loan_rate (
    -- column_id: fcaf6ab1-648c-4f00-8f19-957fddb74a51
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 74bb4d2f-6ba2-4b5c-931b-4378b150f996
    `rate_id` BIGINT NOT NULL COMMENT 'Fineract source column rate_id',
    -- column_id: 67aa70d1-091f-4855-8a8c-4dd9097c7704
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`loan_id`, `rate_id`)
DISTRIBUTED BY HASH(`loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
