-- Reviewed aggregate from dwd_loan_provision_entry
DROP TABLE IF EXISTS retail_banking_dm.dws_loan_provision_run_daily;
-- table_id: 0dee89ae-4fb8-4040-bc22-de5216354b91
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_loan_provision_run_daily (
    -- column_id: 7230346c-dfc7-476a-b662-6422f80d8fd4
    `stat_date` DATE NOT NULL COMMENT 'provisioning_run_created_date',
    -- column_id: 04485ced-4539-49da-964c-2654b52ab164
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 7120e997-0e76-4414-80af-d0135948a03c
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 21481fcd-2640-4a6d-b8a3-2492909d4cb5
    `category_id` BIGINT NOT NULL COMMENT 'Fineract source column category_id',
    -- column_id: f573cb12-9987-446f-985a-5bd51b3b3ed6
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 597be40a-dd0f-4c9a-9647-33453622119d
    `journal_entry_created` BOOLEAN NULL COMMENT 'Whether the provisioning run posted journal entries',
    -- column_id: 2df85855-e66b-419b-ba51-858e0bbbbf4c
    `provision_entry_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 21d83126-e3d2-415e-9387-44f6c166613f
    `total_reserve_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(reseve_amount)',
    -- column_id: 95b608b9-265b-43d8-ac1b-c355a6adb2f8
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `product_id`, `category_id`, `currency_code`, `journal_entry_created`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
