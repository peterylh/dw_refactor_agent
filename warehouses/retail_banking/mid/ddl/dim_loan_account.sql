-- DIM generated from m_loan
DROP TABLE IF EXISTS retail_banking_dm.dim_loan_account;
-- table_id: c09866b8-b93e-4909-a2ae-ca100b0482a7
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_loan_account (
    -- column_id: fa89a10a-82b4-4700-9720-d87b4c89c877
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 526c2bde-41f1-417f-8266-ca1bc695c498
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 66d89755-d407-44e9-b3f4-a1069fb5a43e
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 37f8a6c8-a88a-445e-a60d-30647b5bbe33
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: bfe174c7-ed3c-44b0-99a4-d703c391c23c
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 0128efa0-28d2-4864-84b0-cbbde5fe90e1
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 0f4e33d4-def7-4216-8893-200e0ef988ea
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: d1b2bfb7-2213-4c28-a30d-6614f3fcce43
    `loan_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column loan_type_enum',
    -- column_id: ed558c9f-bdf2-4800-b3bc-9c1058a2306d
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 6a06e9e4-1c73-4c54-9987-c69b3cbceee8
    `loan_transaction_strategy_code` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_code',
    -- column_id: dec3927b-6a93-46b1-88ef-eb3ba6a34fef
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
