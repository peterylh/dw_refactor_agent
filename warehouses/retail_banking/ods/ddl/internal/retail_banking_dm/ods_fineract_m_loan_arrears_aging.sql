-- ODS mirror of Apache Fineract m_loan_arrears_aging (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_arrears_aging;
-- table_id: 2cb4994a-b8f5-4a87-a305-9d86cc71e4fa
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_arrears_aging (
    -- column_id: 053ed172-00bf-485e-a8fb-0e7e7acfe627
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: e7f52500-4934-4731-96cd-a37b59226e93
    `principal_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_overdue_derived',
    -- column_id: 6abed147-b826-4d9d-b1d0-8006274b7a18
    `interest_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_overdue_derived',
    -- column_id: c6606747-9cf1-484b-b58e-b20c6d0359f5
    `fee_charges_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_overdue_derived',
    -- column_id: c5031aaf-2564-4ecb-ae0e-a73e6d1dcc90
    `penalty_charges_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_overdue_derived',
    -- column_id: 7d56f96c-dd56-4693-baf0-005194dd5e99
    `total_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_overdue_derived',
    -- column_id: a94ba99b-cb99-4954-ba3e-1553cfac3190
    `overdue_since_date_derived` DATE NULL COMMENT 'Fineract source column overdue_since_date_derived',
    -- column_id: 16da1787-d099-4fe7-8a3e-598173cb96e7
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`loan_id`)
DISTRIBUTED BY HASH(`loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
