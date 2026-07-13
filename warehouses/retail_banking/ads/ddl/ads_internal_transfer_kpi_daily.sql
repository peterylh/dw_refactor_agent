-- Reviewed application metrics derived from dws_account_transfer_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_internal_transfer_kpi_daily;
-- table_id: 5a4efc39-2fba-49d3-8cc5-0968c43b9cff
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_internal_transfer_kpi_daily (
    -- column_id: 72df3ee4-0e61-4137-846b-f7ed223f961c
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 87ef2154-b809-4585-9e54-a43300709828
    `from_office_id` BIGINT NOT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 14dfb7ae-c56a-4edd-ab0f-ef3763075dd5
    `to_office_id` BIGINT NOT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: a64efef7-e864-49fa-835a-5c378a937efd
    `transfer_type` SMALLINT NULL COMMENT 'Fineract source column transfer_type',
    -- column_id: 064429f1-7cee-4bb3-b0e3-dc2ccc798a8b
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: f15f016d-3355-4cab-8ed8-2de4f63a7458
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: f2946e31-a777-420a-a56d-3d803f0c577f
    `total_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_amount',
    -- column_id: c0e570a8-acae-4840-8050-d2b6d293d7cb
    `average_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_amount / nullif(record_count, 0)',
    -- column_id: 6cee56eb-3d5c-4025-8278-f580439f0142
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `from_office_id`, `to_office_id`, `transfer_type`, `currency_code`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
