-- DIM generated from m_wc_loan
DROP TABLE IF EXISTS retail_banking_dm.dim_wc_loan_account;
-- table_id: be169266-c857-472f-97d7-233aeed43147
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_wc_loan_account (
    -- column_id: 4fa5a4fb-0e3d-41ff-a8b9-82a3505e7349
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0ad83436-3a5d-4598-a236-d93e093a7b95
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: fd06d48e-16ac-4e40-8e7b-56d49ab5ebf1
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: e6f076ae-eb49-42f5-ab64-c174d3e7f18c
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 13191e22-e8da-418b-a427-ac01ec5d64f0
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: 21806dc3-aaa3-4fbe-b1b0-2f4c6919bbd2
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 071f266b-d353-4050-b180-820bca60e698
    `wc_loan_product_id` BIGINT NULL COMMENT 'Fineract source column wc_loan_product_id',
    -- column_id: e93dfb88-ba5b-482a-8cf8-dc1482c889e8
    `currency_code` VARCHAR(3) NULL COMMENT 'Fineract source column currency_code',
    -- column_id: d149d1dd-9bd2-4ee7-996c-1039fb764b39
    `amortization_type` VARCHAR(50) NULL COMMENT 'Fineract source column amortization_type',
    -- column_id: a8aa4cc2-c258-49e9-907d-e8fc5f5f4996
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
