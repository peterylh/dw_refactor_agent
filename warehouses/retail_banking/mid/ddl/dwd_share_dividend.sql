-- DWD generated from m_share_account_dividend_details
DROP TABLE IF EXISTS retail_banking_dm.dwd_share_dividend;
-- table_id: a74971e6-5e85-4948-a3dc-ce4c36f3723b
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_share_dividend (
    -- column_id: 1bdee7e8-7378-4bde-acb6-1f46053e6dd3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 23fd36eb-5005-4088-b992-a68121b869fe
    `dividend_pay_out_id` BIGINT NOT NULL COMMENT 'Fineract source column dividend_pay_out_id',
    -- column_id: b691f480-7100-414e-a387-59befd2904ab
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 87987137-b24b-40ff-98ba-b6fe299bf94f
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 9fa1bfad-ffab-47d9-8763-cfac99721ec7
    `status` SMALLINT NOT NULL COMMENT 'Fineract source column status',
    -- column_id: e3a4d184-b879-49aa-b330-6119db067006
    `savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column savings_transaction_id',
    -- column_id: 712c63e4-c791-4c0b-8157-215866a7a0e3
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 8640dfc9-b8d0-4422-948e-8c6dc299ef6f
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
