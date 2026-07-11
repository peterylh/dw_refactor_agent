-- DWD generated from m_loan_disbursement_detail
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_disbursement;
-- table_id: 70c33430-3e01-47bd-8fbb-26ebb8d943d5
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_disbursement (
    -- column_id: 518d60ce-98cb-4dc1-af2e-8d6d045d69fc
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7148f689-9177-42a2-902b-038e038843e8
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: ee478fd3-66a7-47e9-99f8-4f2824796408
    `expected_disburse_date` DATE NOT NULL COMMENT 'Fineract source column expected_disburse_date',
    -- column_id: 2fa8e86f-b9f8-4469-8828-23b5e2363db1
    `disbursedon_date` DATE NULL COMMENT 'Fineract source column disbursedon_date',
    -- column_id: eced417e-03e0-4e65-a276-f71216aeb6f1
    `principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal',
    -- column_id: a226c7e0-e4fa-436f-a3b5-e449e53d5b60
    `net_disbursal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column net_disbursal_amount',
    -- column_id: a4821b59-4541-4997-afe3-559fbe5c4b13
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: c9b20ff6-91b9-4c59-b512-7e88656cfd49
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: aedc4002-e358-4d6f-a408-fc5c2ae4a394
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
