-- ODS mirror of Apache Fineract m_loan_account_locks (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_account_locks;
-- table_id: f58fd1fb-5bef-4d5f-acf7-5496a2717503
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_account_locks (
    -- column_id: 4e48c0e3-5c7d-4533-9346-23bd75b243c3
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: c3fb835f-a19c-4d88-966d-caeff6557324
    `lock_owner` VARCHAR(100) NOT NULL COMMENT 'Fineract source column lock_owner',
    -- column_id: 63fc079b-92eb-4c69-ae2b-fd03fae6cfb0
    `error` VARCHAR(255) NULL COMMENT 'Fineract source column error',
    -- column_id: 129710b3-b0f9-4b0a-94bf-599ec54ca523
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 0272c4c9-0856-4f9f-831c-fdd856a4c3d8
    `stacktrace` STRING NULL COMMENT 'Fineract source column stacktrace',
    -- column_id: 63fc1ebc-9735-4a68-9841-b6c9f9fa7834
    `lock_placed_on` DATETIME NOT NULL COMMENT 'Fineract source column lock_placed_on',
    -- column_id: a8e7dfca-523d-4253-97b2-f4b154674bc1
    `lock_placed_on_cob_business_date` DATE NULL COMMENT 'Fineract source column lock_placed_on_cob_business_date',
    -- column_id: b92fab7a-754e-4b41-bc2d-72feee83db3e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`loan_id`)
DISTRIBUTED BY HASH(`loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
