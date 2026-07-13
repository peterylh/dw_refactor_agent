-- ODS mirror of Apache Fineract m_wc_loan_account_locks (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_account_locks;
-- table_id: 78a0e038-5e98-4776-873a-f77c4b1c9abd
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_account_locks (
    -- column_id: a9dd1995-490b-464c-8bd7-0bfbe82dcc42
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: da3c437c-b86a-4221-8a81-007bffe95b0b
    `version` BIGINT NULL COMMENT 'Fineract source column version',
    -- column_id: fc3ed517-3e89-4f02-975f-40b5c3786980
    `lock_owner` VARCHAR(100) NOT NULL COMMENT 'Fineract source column lock_owner',
    -- column_id: e58759aa-0554-44b9-9a4b-b01cc9719659
    `lock_placed_on` DATETIME NOT NULL COMMENT 'Fineract source column lock_placed_on',
    -- column_id: 69772b98-a81d-4557-9da3-6bc0d5b9fa6f
    `error` VARCHAR(255) NULL COMMENT 'Fineract source column error',
    -- column_id: c1924e72-a886-4e01-9867-fa79536d011f
    `stacktrace` STRING NULL COMMENT 'Fineract source column stacktrace',
    -- column_id: 01c4d53d-aec5-4d61-84ec-d87231edfb1e
    `lock_placed_on_cob_business_date` DATE NULL COMMENT 'Fineract source column lock_placed_on_cob_business_date',
    -- column_id: 82a90216-c437-4656-906f-4b4ff3395e7c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`loan_id`)
DISTRIBUTED BY HASH(`loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
