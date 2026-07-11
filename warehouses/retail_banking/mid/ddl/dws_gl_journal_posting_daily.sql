-- Reviewed aggregate from dwd_gl_journal_entry
DROP TABLE IF EXISTS retail_banking_dm.dws_gl_journal_posting_daily;
-- table_id: 4c33fb3c-3139-4cd2-b7b6-d427eaa0bc9c
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_gl_journal_posting_daily (
    -- column_id: 47c343f8-4bdf-48cb-b811-5f8da5ce8046
    `stat_date` DATE NOT NULL COMMENT 'posting_date',
    -- column_id: 71269894-d2e8-48b8-aa76-fb236820b82f
    `transaction_id` VARCHAR(50) NOT NULL COMMENT 'Fineract source column transaction_id',
    -- column_id: ca034355-82ef-4ef7-819b-654ebe734b0d
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 498d1b80-8d41-476c-9b14-4cc21f46dc16
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 27cc5e6d-e9f7-4c68-b877-ec5b504ab435
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 5b7a5171-e91f-4cce-87c0-2842a3840ecd
    `type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: d21a6793-3758-48ca-b9d9-d436359095bf
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: baaeb7a6-9818-4368-86c6-30bd167de8a9
    `total_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: e57088dc-f496-48c9-91ad-97d96015564b
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `transaction_id`, `office_id`, `account_id`, `currency_code`, `type_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
