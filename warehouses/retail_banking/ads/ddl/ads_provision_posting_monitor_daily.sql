-- Reviewed application metrics derived from dws_loan_provision_run_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_provision_posting_monitor_daily;
-- table_id: 74d90e1f-9e6a-4564-952a-a823524be825
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_provision_posting_monitor_daily (
    -- column_id: 9aa1405c-62b0-4925-b51f-1aed785597b7
    `stat_date` DATE NOT NULL COMMENT 'provisioning_run_created_date',
    -- column_id: 51c0f3d4-6b59-48e2-aed0-c5aefcb85169
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: d00dbec7-7492-4cc5-80fc-4fc06e0607c2
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 510a298e-a0e6-4560-ac84-4971517580b1
    `category_id` BIGINT NOT NULL COMMENT 'Fineract source column category_id',
    -- column_id: 107ff1e1-f0b3-420e-861b-a5772e57bcdb
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 49f40f2f-ade1-470e-b7ea-e23bb65e2042
    `provision_entry_count` BIGINT NULL COMMENT 'derived metric: sum(provision_entry_count)',
    -- column_id: 03b625a2-607c-4790-a267-7776d72ca99e
    `total_reserve_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: sum(total_reserve_amount)',
    -- column_id: dbca6b7c-990c-4e65-8219-c6034ae11b83
    `unposted_entry_count` BIGINT NULL COMMENT 'calculated metric: sum(case when coalesce(journal_entry_created, false) = false then provision_entry_count else 0 end)',
    -- column_id: 4fc8f376-1da2-4692-85c8-d5df98da6d97
    `unposted_reserve_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: sum(case when coalesce(journal_entry_created, false) = false then total_reserve_amount else 0 end)',
    -- column_id: 6e310bf0-a21e-4106-a22c-82b3d16e421f
    `posting_ratio` DECIMAL(38,6) NULL COMMENT 'calculated metric: 1 - unposted_entry_count / nullif(provision_entry_count, 0)',
    -- column_id: 51810caa-9858-4b39-b1bb-417c3e0fd6f8
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `product_id`, `category_id`, `currency_code`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
