-- Reviewed application metrics derived from dws_gl_journal_posting_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_gl_posting_reconciliation_daily;
-- table_id: ef27367f-779a-4f06-bf4f-c97a73609455
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_gl_posting_reconciliation_daily (
    -- column_id: abb47cf1-d2f7-42fd-acc9-2abb72133cd6
    `stat_date` DATE NOT NULL COMMENT 'posting_date',
    -- column_id: 888a9f1c-bd45-4a7b-ba81-78a4c6a1fe8f
    `transaction_id` VARCHAR(50) NOT NULL COMMENT 'Fineract source column transaction_id',
    -- column_id: 2ac06699-4dc3-4fae-ba2d-425b82b15341
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: f95d3473-25a1-4905-a014-9466f5a84f60
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 9acf172e-6115-48ee-a678-bb63a4c8ea3d
    `debit_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: sum(case when type_enum = 1 then total_amount else 0 end)',
    -- column_id: 25590ce8-391e-4148-89fe-3cd367be17cd
    `credit_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: sum(case when type_enum = 2 then total_amount else 0 end)',
    -- column_id: e9ef9925-c08f-43f7-8c6a-d15790ef32f1
    `imbalance_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: debit_amount - credit_amount',
    -- column_id: 62ce1b35-a66e-434d-ba00-66c855f7bea1
    `is_balanced` BOOLEAN NULL COMMENT 'calculated metric: abs(imbalance_amount) <= reconciliation_tolerance',
    -- column_id: 9a6ed3aa-bd7e-4423-b820-55ca6c8257ce
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `transaction_id`, `office_id`, `currency_code`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
