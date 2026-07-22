-- Reviewed aggregate from dwd_wc_breach_event
DROP TABLE IF EXISTS retail_banking_dm.dws_wc_breach_start_daily;
-- table_id: dc7169c1-491b-4590-ac2e-49cfb1d891af
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_wc_breach_start_daily (
    -- column_id: 35d1b13f-72b1-4694-9d08-422a1fd94bd1
    `stat_date` DATE NOT NULL COMMENT 'event_start_date',
    -- column_id: d1c8d330-f492-4400-a9a6-75f1b2dd3ef5
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 5b6ed6f5-83ca-49dc-9eca-157a0f837dd7
    `action` VARCHAR(128) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: 04c75e4e-28fc-445c-bcb8-523d434e47ae
    `breach_start_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 8e061ae7-5d72-4ee1-998d-6be701d2f1d2
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `wc_loan_id`, `action`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
