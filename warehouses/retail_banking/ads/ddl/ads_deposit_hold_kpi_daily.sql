-- Reviewed application metrics derived from dws_deposit_hold_event_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_deposit_hold_kpi_daily;
-- table_id: bafe8ee2-c180-4e3a-9b9c-922d9dcb3c62
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_deposit_hold_kpi_daily (
    -- column_id: b204e179-cc46-448f-8e70-7a558fd8b3e7
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 5156dfb7-bd26-4a3b-b705-875bf9866f6f
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 0ebffe08-977b-4838-b8c6-325524efb7cf
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: f7a983c4-1eba-4e3a-ad0f-527e01a76c25
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: e8079ff7-ec89-4ced-9713-da22f1e623dd
    `total_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_amount',
    -- column_id: 6e810c16-c28b-4e43-ae6d-ddbbeff87645
    `average_hold_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_amount / nullif(record_count, 0)',
    -- column_id: 023cb85e-84e5-4c6a-b05a-29a75b15f2a7
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `savings_account_id`, `transaction_type_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
