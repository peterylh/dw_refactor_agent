-- Reviewed aggregate from dwd_deposit_hold_event
DROP TABLE IF EXISTS retail_banking_dm.dws_deposit_hold_event_daily;
-- table_id: 36fb294f-3a94-4479-ad71-9d72400af85f
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_deposit_hold_event_daily (
    -- column_id: 8b16c677-d3fc-40fd-a449-bacbe1cfd960
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: caad8668-1904-45d7-9c17-fdc76b9b28b2
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 3d356ff4-20b5-447b-9664-6b778d2cfb74
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: c79fd840-686e-44be-b01a-937324c78bf4
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: caf909af-64fc-49a8-b31c-6982ce77be5c
    `total_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: 80685723-8509-422c-b243-06b3a4cf5249
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `savings_account_id`, `transaction_type_enum`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
