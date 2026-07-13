-- DWD generated from m_savings_account_transaction_tax_details
DROP TABLE IF EXISTS retail_banking_dm.dwd_deposit_transaction_tax;
-- table_id: 29104858-999f-4b8f-9b56-ace1ed1835f3
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_deposit_transaction_tax (
    -- column_id: 0259eea4-517f-4858-a3f8-1a51e356dd2c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: be119876-30a9-480c-aacb-cfaaf79d2753
    `savings_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_transaction_id',
    -- column_id: 9c1a8656-9ba6-4482-a4d1-8f033587d7e2
    `tax_component_id` BIGINT NOT NULL COMMENT 'Fineract source column tax_component_id',
    -- column_id: c67f08c5-1a3d-41d1-b977-07bff418a204
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 6b6fdf78-2ab9-40c8-8e2d-ae4e176b9bf8
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 3c304834-e09d-4e9d-9828-27722059d38d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
