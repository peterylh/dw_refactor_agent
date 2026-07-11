-- ODS mirror of Apache Fineract m_loan_topup (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_topup;
-- table_id: c5f8ad8a-dceb-434d-8da7-738ffd209b0a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_topup (
    -- column_id: c622a0eb-d639-4e31-b9a6-185943054256
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6f94036f-6b92-41e4-8874-96a2112367d8
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 6a6a9212-c65c-4d43-b14b-a9f278e0a277
    `closure_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column closure_loan_id',
    -- column_id: 1eaa40cb-1632-4366-946f-01d64e454342
    `account_transfer_details_id` BIGINT NULL COMMENT 'Fineract source column account_transfer_details_id',
    -- column_id: 3f57e6e5-9f7a-4f28-a7b7-d028c789b40c
    `topup_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column topup_amount',
    -- column_id: c62bf0f4-8c8e-4736-9375-a530adf9c366
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
