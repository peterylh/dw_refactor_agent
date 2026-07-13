-- ODS mirror of Apache Fineract m_wc_loan_delinquency_range_schedule (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_delinquency_range_schedule;
-- table_id: 48854109-4a8f-48c3-b69b-dc2b5e01edf0
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_delinquency_range_schedule (
    -- column_id: 861d3700-fda2-4467-9a36-939e069dfa75
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4d06bfdd-8160-49ea-ba2b-c0adc0667983
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: a95afd2b-c67e-4c00-96d6-3453aaf3dc7e
    `period_number` INT NOT NULL COMMENT 'Fineract source column period_number',
    -- column_id: 1229bd1f-e057-4385-824d-420229f8e179
    `from_date` DATE NOT NULL COMMENT 'Fineract source column from_date',
    -- column_id: d5615c98-0f50-4b93-abe3-fb7ece7576d6
    `to_date` DATE NOT NULL COMMENT 'Fineract source column to_date',
    -- column_id: 2dedf813-ef6f-42c1-9058-9f2241b5396f
    `expected_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column expected_amount',
    -- column_id: 3755f07a-4127-492c-b39c-53fa2d69f009
    `paid_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column paid_amount',
    -- column_id: cacd6655-d5ba-4e9d-af2e-b1d8b09e8d9b
    `outstanding_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column outstanding_amount',
    -- column_id: 4d3c267c-e2d4-45f3-837c-a2973b33e9e8
    `min_payment_criteria_met` BOOLEAN NULL COMMENT 'Fineract source column min_payment_criteria_met',
    -- column_id: 20720b53-f35c-4dc2-97c0-e4a7d6d9d909
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 1b551a6e-4ec6-4918-8802-49a99561fcd6
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: cc649c80-bf06-4cac-9a96-98bde5437aee
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 1f2c2942-c8a9-4ef4-8868-1bbb2a7f7922
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 09077c8e-18d1-4e09-be60-edad4c3cfdf9
    `delinquent_days` BIGINT NULL COMMENT 'Fineract source column delinquent_days',
    -- column_id: 4f77632d-7d7c-4130-9c0f-b9eeae4fb11f
    `delinquent_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column delinquent_amount',
    -- column_id: f6e1132c-ef59-45ea-bac7-4d28486f1c83
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: f68c3547-45ac-4378-9e0e-71ad4f6415a7
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
