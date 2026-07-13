-- Reviewed application metrics derived from dws_wc_loan_transaction_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_wc_transaction_kpi_daily;
-- table_id: 39bf78c0-5d64-48b5-a0fa-b3d88df98ae9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_wc_transaction_kpi_daily (
    -- column_id: 7dadbd8a-726f-4420-a168-604fc3914caa
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: e60a6124-a94c-4a63-bf44-55ad1f87628d
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 845544c4-aae9-4917-8d3e-848a5794c948
    `transaction_type_id` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_id',
    -- column_id: 74041de9-52fd-454d-acd7-0b1d1e067eb8
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: f5f15b53-27b8-4e07-aea7-2f58f20897ee
    `total_transaction_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_transaction_amount',
    -- column_id: 9414f11d-c909-47bf-8467-c6219756cf80
    `average_transaction_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_transaction_amount / nullif(record_count, 0)',
    -- column_id: 69b28ea2-9cac-4428-9707-d074178035d2
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `wc_loan_id`, `transaction_type_id`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
