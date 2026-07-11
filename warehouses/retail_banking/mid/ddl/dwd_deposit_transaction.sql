-- DWD generated from m_savings_account_transaction
DROP TABLE IF EXISTS retail_banking_dm.dwd_deposit_transaction;
-- table_id: f489d850-f930-4930-b4d5-60bd992c96e1
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_deposit_transaction (
    -- column_id: 1db1d420-532e-49ad-a32b-76d14125671e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 28f9e7b0-b351-4355-bad4-f1837c0211a9
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: f7470666-be22-49fe-a853-a51c4325fde7
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: c6826f68-2ce4-4ceb-9fcd-3b6724a2f815
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: 6d640dac-08e2-485e-9f2a-ae4c3e3c87b2
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 3fb29d59-12bb-4f45-9c8f-f1b377cbb5b0
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: b25e566b-d06d-438a-8543-463d77b34e5c
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: d2515a66-becf-4414-828f-97b51d504166
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: f782f75e-b2d5-40e6-9ae4-c12d9a614772
    `overdraft_amount_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column overdraft_amount_derived',
    -- column_id: ac8a0d0d-d716-468b-b8e7-c3d8fd7f4ddf
    `balance_end_date_derived` DATE NULL COMMENT 'Fineract source column balance_end_date_derived',
    -- column_id: 20aa62ef-1060-4313-90da-a67037a3a1b9
    `balance_number_of_days_derived` INT NULL COMMENT 'Fineract source column balance_number_of_days_derived',
    -- column_id: 702f01d7-ff0d-426b-bc62-5357104f953e
    `running_balance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column running_balance_derived',
    -- column_id: b0eb58f4-d580-4bc0-a272-444db17cef8e
    `cumulative_balance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column cumulative_balance_derived',
    -- column_id: c5a85060-c1ab-44c9-90bb-d50616d78a24
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: de9e9150-b164-4e93-971e-de4a7e9dd0f9
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 033cbafd-cc93-402b-b94a-6ec632150abd
    `is_manual` BOOLEAN NULL COMMENT 'Fineract source column is_manual',
    -- column_id: ecd47906-22fe-431a-aae5-b1112f255a81
    `release_id_of_hold_amount` BIGINT NULL COMMENT 'Fineract source column release_id_of_hold_amount',
    -- column_id: 35a591ea-0a89-46a2-ba22-130c37d100d0
    `is_loan_disbursement` BOOLEAN NULL COMMENT 'Fineract source column is_loan_disbursement',
    -- column_id: 03633971-cb7f-41e1-a517-d38c080bfc10
    `ref_no` VARCHAR(128) NULL COMMENT 'Fineract source column ref_no',
    -- column_id: 8421dc41-7dd8-4ded-b8c2-fc8b32154bc5
    `original_transaction_id` BIGINT NULL COMMENT 'Fineract source column original_transaction_id',
    -- column_id: 5fd78724-17cd-4235-aab1-f0ed0499a8d7
    `is_reversal` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversal',
    -- column_id: 82db3199-5f3e-4721-a7f7-f7a6af9b99bc
    `reason_for_block` VARCHAR(256) NULL COMMENT 'Fineract source column reason_for_block',
    -- column_id: b47ff696-b5c7-4850-b00e-9b9465e29df7
    `is_lien_transaction` BOOLEAN NOT NULL COMMENT 'Fineract source column is_lien_transaction',
    -- column_id: 85150724-6cf3-486b-b3a1-e002fb95aba9
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 38c01a7d-004f-4ac9-93b5-8baaa9753a2c
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 84582257-fdba-4bae-9efa-c23096b61fed
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: dd887f4a-b28e-4fcb-a6f7-be1bb50aed5b
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 49f1c177-547a-4324-aa3a-76d604f10fb8
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 4a7d8cd3-5e61-45b2-99b7-fd9d7929e7be
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: ee1f9a79-8ffb-4e05-9d8d-43be13a9a3d8
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
