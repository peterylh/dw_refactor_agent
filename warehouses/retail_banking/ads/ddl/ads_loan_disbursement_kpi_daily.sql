-- Reviewed application metrics derived from dws_loan_disbursement_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_loan_disbursement_kpi_daily;
-- table_id: c52edabc-7186-4f56-925c-ea43a5ac437a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_loan_disbursement_kpi_daily (
    -- column_id: c7388db9-d85a-480f-8eba-fb83ecd4219e
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 9211be01-08d9-4310-9d5c-8a70dfe71f06
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 5788976b-96f0-45e8-b9e3-83873ab29869
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: 12827f63-2655-4516-af16-f0f130edab50
    `total_principal` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_principal',
    -- column_id: 64e30413-88c8-4816-a507-9a6ee0c26f27
    `total_net_disbursal_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_net_disbursal_amount',
    -- column_id: 1a167ae7-fc91-42fe-9448-abddf2c729aa
    `average_principal` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_principal / nullif(record_count, 0)',
    -- column_id: 4f6e7424-f8c7-4488-bb7e-7c21840308ba
    `net_disbursal_ratio` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_net_disbursal_amount / nullif(total_principal, 0)',
    -- column_id: 1e30e48b-8710-4008-a276-171b53099620
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `loan_id`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
