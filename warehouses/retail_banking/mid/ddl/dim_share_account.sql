-- DIM generated from m_share_account
DROP TABLE IF EXISTS retail_banking_dm.dim_share_account;
-- table_id: 18c3ba3b-cfcf-43ae-b532-a94309ae131a
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_share_account (
    -- column_id: 60aff9ce-5942-4c58-9aed-bf2509e88e57
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2b5f81f7-f03c-4702-b51d-a9a0e3ca53fd
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 36e5aacd-0725-4d48-a8bb-5a4687df22ab
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 92a94036-eb1a-4cde-9d65-96c5248c57b0
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 5ad4a28e-79cd-47b0-b141-e6ac69a93d35
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 8ad18397-742c-480f-a5fc-8a5dab1a8d69
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 51830358-f2fd-4f6a-bd57-ab863a5cc706
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 617aec4e-2d2d-4f78-a979-5846633e372e
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
