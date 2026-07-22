SET allow_partition_column_nullable = true;

-- DWD generated from m_guarantor_transaction
DROP TABLE IF EXISTS retail_banking_dm.bridge_guarantee_transaction;
-- table_id: 96659559-0119-4285-a3b7-f1b633625188
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_guarantee_transaction (
    -- column_id: c7751506-f50d-4a18-9140-7b6075e5afd5
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9470102d-429b-4845-8c81-53b2769a1510
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 660f1bf2-7dc3-4686-8838-914bfaffe30e
    `guarantor_fund_detail_id` BIGINT NOT NULL COMMENT 'Fineract source column guarantor_fund_detail_id',
    -- column_id: 96bf6521-c7e5-490b-98f6-c869e34aadcd
    `loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 4b9c0fc1-2636-4f9f-808e-2e18124c8316
    `deposit_on_hold_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column deposit_on_hold_transaction_id',
    -- column_id: 008832d9-3d58-45fe-9a48-98831f98be95
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 466d1d30-93c3-41ac-95c9-3bf86f7c4ec1
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
