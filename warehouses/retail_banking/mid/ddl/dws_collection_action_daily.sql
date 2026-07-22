-- Reviewed aggregate from dwd_collection_action
DROP TABLE IF EXISTS retail_banking_dm.dws_collection_action_daily;
-- table_id: 989063bc-ed94-4c3f-8e9c-bb2ed62d1aee
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_collection_action_daily (
    -- column_id: d85c50f0-dbd8-444a-b997-62cd089b9a85
    `stat_date` DATE NOT NULL COMMENT 'event_start_date',
    -- column_id: ad44fb36-0872-4838-b80b-da02fbddea5d
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: b92607ae-df1d-4170-9895-89c01d98ba0f
    `action` VARCHAR(128) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: 271da9e7-9dc4-4521-95e1-9d817e175e11
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 2495f288-7d11-47c6-8393-bf6f52031669
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `loan_id`, `action`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
