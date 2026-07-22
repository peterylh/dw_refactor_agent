-- Reviewed aggregate from dwd_loan_delinquency_event
DROP TABLE IF EXISTS retail_banking_dm.dws_loan_delinquency_entry_daily;
-- table_id: 543e1f92-fd83-4e4d-b897-4ac4d0f6cd78
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_loan_delinquency_entry_daily (
    -- column_id: 2c1302a5-98dd-4480-9e38-582a04096a88
    `stat_date` DATE NOT NULL COMMENT 'event_entry_date',
    -- column_id: c568babc-3e5e-42aa-9a5b-700a2c85574b
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 0064eef2-7df9-46de-a78d-47494b0243f6
    `delinquency_range_id` BIGINT NOT NULL COMMENT 'Fineract source column delinquency_range_id',
    -- column_id: 4254b99f-abfa-42d0-bde5-6d2bb41ff969
    `entry_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: f5abf628-2701-4678-be85-87721a0bca40
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `loan_id`, `delinquency_range_id`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
