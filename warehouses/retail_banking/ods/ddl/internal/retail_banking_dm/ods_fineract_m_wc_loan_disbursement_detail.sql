-- ODS mirror of Apache Fineract m_wc_loan_disbursement_detail (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_disbursement_detail;
-- table_id: 74a52263-da26-45b2-b3f8-e16dd387ea8c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_disbursement_detail (
    -- column_id: ed015527-81f1-4e8e-853f-efba73a59623
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5466503c-ec50-4845-b5b2-d99ec4b5f7e5
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 321cc12d-5d29-47d4-9e0c-5cc3f36b289d
    `expected_disburse_date` DATE NULL COMMENT 'Fineract source column expected_disburse_date',
    -- column_id: 6164579f-978f-4559-9c62-c5b2c71a53b8
    `expected_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column expected_amount',
    -- column_id: 27ec33d7-73f9-414d-bd7b-2eea1e8039e0
    `expected_maturity_date` DATE NULL COMMENT 'Fineract source column expected_maturity_date',
    -- column_id: 8c69667d-18c2-4dd1-b1c1-0e89cefc7041
    `actual_disburse_date` DATE NULL COMMENT 'Fineract source column actual_disburse_date',
    -- column_id: 54120d46-eb94-4648-b084-0942db745ae9
    `actual_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column actual_amount',
    -- column_id: 8b91e377-f595-4b6c-8399-a3a911ab3ea4
    `disbursedon_userid` BIGINT NULL COMMENT 'Fineract source column disbursedon_userid',
    -- column_id: ea49ffc4-36c5-4771-bd80-951876faab96
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
