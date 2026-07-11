-- ODS mirror of Apache Fineract m_wc_loan_transaction_allocation (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_transaction_allocation;
-- table_id: 8a338e22-bf19-4b14-b174-3152b56d0ba7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_transaction_allocation (
    -- column_id: ea963e5c-8660-4ba6-8ede-11b5191b99b3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bd2ba8de-3eeb-4e27-8b21-dc6fec5a3d63
    `wc_loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_transaction_id',
    -- column_id: bbf410ed-d5e1-4fec-ad90-a05d50fe2a86
    `principal_portion` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_portion',
    -- column_id: 7e63634b-502a-4835-a0db-a8045d2691d8
    `fee_charges_portion` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_portion',
    -- column_id: fa84e92b-c09c-423f-ba85-fde98ea7a305
    `penalty_charges_portion` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_portion',
    -- column_id: 038933fb-25dd-4977-8f13-e2e2983424fe
    `version` SMALLINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: b0087cce-870a-485b-8143-af4ccf0c0b8e
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 37bbff5a-1c7f-4ecf-9bd3-863b70976068
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: e90917ec-c93c-4350-89f5-4a29eedfa464
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: ce44bf10-0cd3-40b4-b5a6-0678a1ae515b
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c6bb2671-a299-495f-ba89-efb0a7d43e4a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
