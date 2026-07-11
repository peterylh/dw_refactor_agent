-- ODS mirror of Apache Fineract m_loan_interest_recalculation_additional_details (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_interest_recalculation_additional_details;
-- table_id: ea47cf94-518f-4443-8de9-4ca925c84174
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_interest_recalculation_additional_details (
    -- column_id: 46d2c0dc-2145-469d-a25e-7f712d3742d1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c5a4dbf6-0bd4-4ecb-9895-8bc9b7e82dc0
    `loan_repayment_schedule_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_repayment_schedule_id',
    -- column_id: c32210e0-8966-422e-923d-61428800a06f
    `effective_date` DATE NOT NULL COMMENT 'Fineract source column effective_date',
    -- column_id: 3c470ff5-a08e-4c33-a0c8-cd91fff17ccc
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 1f822e59-024a-4032-bbe0-7502cb585c0a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
