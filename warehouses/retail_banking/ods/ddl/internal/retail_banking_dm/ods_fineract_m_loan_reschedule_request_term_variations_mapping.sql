-- ODS mirror of Apache Fineract m_loan_reschedule_request_term_variations_mapping (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_reschedule_request_term_variations_mapping;
-- table_id: ff5804de-ed43-482f-b116-9fa28958d39d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_reschedule_request_term_variations_mapping (
    -- column_id: 05659dc7-d760-4e9c-92de-3c09f3a4d07a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 41ccdcb2-2b41-4393-9f8b-2015651daf9f
    `loan_reschedule_request_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_reschedule_request_id',
    -- column_id: d9a4b51b-c44b-4cfd-9435-04dac48111b2
    `loan_term_variations_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_term_variations_id',
    -- column_id: c3b97960-4ca5-4415-b380-9b2020012469
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
