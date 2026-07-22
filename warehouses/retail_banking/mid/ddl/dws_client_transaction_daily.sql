-- Reviewed aggregate from dwd_client_transaction
DROP TABLE IF EXISTS retail_banking_dm.dws_client_transaction_daily;
-- table_id: bf0ce92e-8736-4ec7-ba7f-4e320ffc98c3
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_client_transaction_daily (
    -- column_id: aedc8e91-adfd-4c3e-8044-7b624c88ff03
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 78aa7a7d-7a43-4cac-896e-8f4f4c7c7b78
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: e275cd1e-51f1-4e5b-82e2-079ad5de38f0
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: ca35d5af-aaa8-48a4-b2b0-e2c7813ab02c
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: bef4b107-d5dd-44f4-b78f-0e04db08a572
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: a9d85dce-7bbe-4736-bd33-7894278ba617
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 6c5016b3-9be2-48dd-abea-33abe822dccd
    `total_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: a283e315-12cf-4cca-9b4e-c007e9147b51
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `client_id`, `currency_code`, `transaction_type_enum`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
