SET allow_partition_column_nullable = true;

-- DWD generated from m_trial_balance
DROP TABLE IF EXISTS retail_banking_dm.dwd_gl_trial_balance_snapshot;
-- table_id: 5b9be95a-179f-4a46-a578-860841ed4dc5
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_gl_trial_balance_snapshot (
    -- column_id: 996dea94-3a43-4c0a-8faf-3b77f57f4dcb
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 0975f7f8-c184-42ce-a1b5-78ee881584bb
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: d565af2f-3ed7-441c-82fa-76bddc7c1626
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: f33e1cec-6cb9-4833-9d8f-244fb6f156ab
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: e376b6ba-6357-4522-b268-da629520c351
    `entry_date` DATE NOT NULL COMMENT 'Fineract source column entry_date',
    -- column_id: 23817a68-ea02-492d-b026-887c4ae0caa4
    `created_date` DATE NULL COMMENT 'Fineract source column created_date',
    -- column_id: d8b6a32a-35e8-41cb-810b-8d1369e2bc85
    `closing_balance` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column closing_balance',
    -- column_id: e8c64312-19e0-4f2b-bc65-14d06a3bb766
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`office_id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`office_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
