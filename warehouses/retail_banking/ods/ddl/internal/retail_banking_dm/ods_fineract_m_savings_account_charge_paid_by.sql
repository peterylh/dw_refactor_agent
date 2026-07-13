-- ODS mirror of Apache Fineract m_savings_account_charge_paid_by (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_account_charge_paid_by;
-- table_id: aecc94c6-b65a-462f-9c51-6419b0789815
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_account_charge_paid_by (
    -- column_id: fb180b47-bf61-43a5-8d85-035d1d8fe24e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cbe64ce4-496e-40b8-a4fc-01285a25560f
    `savings_account_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_transaction_id',
    -- column_id: 485f3ef1-9b79-4793-81ca-4d640f5beb3f
    `savings_account_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_charge_id',
    -- column_id: 7e362b8a-8a80-454c-8909-b076d8d631ee
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 1d992937-3289-44d3-9d35-e66e548645b0
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
