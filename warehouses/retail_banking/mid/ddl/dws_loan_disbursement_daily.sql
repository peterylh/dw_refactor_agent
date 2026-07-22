-- Reviewed aggregate from dwd_loan_disbursement
DROP TABLE IF EXISTS retail_banking_dm.dws_loan_disbursement_daily;
-- table_id: 3986b234-73bc-499a-8959-50693345a0ce
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_loan_disbursement_daily (
    -- column_id: 07d29375-c71c-43c1-8a74-69ddfdfe5ef0
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: b641031d-851f-4ac6-9461-38675dd1dcba
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: be8a19d4-da3c-4997-aad8-313736dc86ea
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 613e4622-a46f-48da-9a51-a22e760e80f8
    `total_principal` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(principal)',
    -- column_id: f1ecd01d-060a-4bbf-b9f9-712addafcf10
    `total_net_disbursal_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(net_disbursal_amount)',
    -- column_id: a6c5b975-c271-4f04-afc9-f8c132a4c6e0
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `loan_id`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
