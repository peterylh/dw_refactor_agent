SET allow_partition_column_nullable = true;

-- DWD generated from m_external_asset_owner_transfer_details
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_ownership_transfer_detail;
-- table_id: aee03578-2527-415b-b4ca-ac9fce20cf78
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_ownership_transfer_detail (
    -- column_id: 0865bcd4-7d7f-48ed-b481-c260a2756400
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 806a011e-3a8d-4697-8111-35e6547f61ff
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: ef954c2e-0435-48e5-ac26-e29dab4922e1
    `asset_owner_transfer_id` BIGINT NOT NULL COMMENT 'Id of asset owner transfer',
    -- column_id: c1cabe69-1067-4ec8-ba5e-3e7ae8439c07
    `total_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_outstanding_derived',
    -- column_id: e2df141a-adc5-4371-9d0c-479021b45582
    `principal_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_outstanding_derived',
    -- column_id: 2ae563ca-87ef-48de-995e-1d99a8cfb9f9
    `interest_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_outstanding_derived',
    -- column_id: 681e7114-ad0b-4243-8c9f-2b237a1fe4e0
    `fee_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_outstanding_derived',
    -- column_id: c843a184-6fba-4a72-ba70-810aca120406
    `penalty_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_outstanding_derived',
    -- column_id: 2bf4d1c5-9249-400f-be7b-46a1be518754
    `total_overpaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_overpaid_derived',
    -- column_id: 05777fc4-1787-4e0a-af67-8c1fe33b6d26
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: e77ddca6-319e-480a-95f2-5afb82b9b4e4
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: ccdfda6c-8dec-44ba-bade-6ebe4f2cb9b5
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 91daa533-9c53-46be-aed0-97785fd68177
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: bccef3cf-a22c-4c9d-a7b4-87debba18d43
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
