-- ODS mirror of Apache Fineract m_loan_disbursement_detail (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_disbursement_detail;
-- table_id: ccf72ed0-1a94-4a28-8726-aeab514b5a67
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_disbursement_detail (
    -- column_id: f12653c9-f39d-4438-85b7-b4a8d6034688
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cd414bdc-fafd-422a-b9f6-9bcaacf7060f
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 2ced6e96-4aa0-4928-90cc-b70dc4f764f6
    `expected_disburse_date` DATE NOT NULL COMMENT 'Fineract source column expected_disburse_date',
    -- column_id: 42312488-3ba6-46cc-a628-938640eca6e9
    `disbursedon_date` DATE NULL COMMENT 'Fineract source column disbursedon_date',
    -- column_id: b034a6d3-fc2f-4621-9f92-14dc37705edd
    `principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal',
    -- column_id: a2251156-7165-44e8-a07e-454ed3329625
    `net_disbursal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column net_disbursal_amount',
    -- column_id: 7bf925c9-e8e9-4942-a0cd-51d43f4e5a0c
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 987e304b-ac9e-4b0b-8c41-5e1ef5be148e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
