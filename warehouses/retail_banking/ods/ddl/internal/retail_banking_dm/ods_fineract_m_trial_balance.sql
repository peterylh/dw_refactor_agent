-- ODS mirror of Apache Fineract m_trial_balance (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_trial_balance;
-- table_id: 6ac05d4a-171b-4513-aab2-0eebda3afbab
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_trial_balance (
    -- column_id: 93d74dd2-b77c-43cd-b6ce-703a9abccffb
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 4e035019-1f85-46cf-8650-e4e8c556d842
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 17e74e4a-40fb-429b-b506-3bc3090029a9
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 872b0385-5d3d-404f-bf7c-4351e6809371
    `entry_date` DATE NOT NULL COMMENT 'Fineract source column entry_date',
    -- column_id: 41daa3bd-a5d2-4ea8-8f76-6d1d03709936
    `created_date` DATE NULL COMMENT 'Fineract source column created_date',
    -- column_id: 22c0429a-f4c1-42a0-a196-431d8e6a98c1
    `closing_balance` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column closing_balance',
    -- column_id: 5c9a7a73-4c28-4d49-93f5-b7ab9d013fde
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`office_id`)
DISTRIBUTED BY HASH(`office_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
