-- ODS mirror of Apache Fineract m_savings_account_transaction (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_account_transaction;
-- table_id: 33855f9f-5df6-4a34-b4b9-574c89c287ca
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_account_transaction (
    -- column_id: a1e52d12-b13b-4381-89bb-c83b6e27ed7e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: be4b7619-700c-46f1-ab06-6e892120f062
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: c0db2cc2-97f1-41f4-b3f7-4550004107c8
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 829c3153-3a03-4066-9f54-14cfefd95be2
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: 2337bc04-e4b8-4d09-9569-6c2440d725c7
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 74325ee0-b134-49b4-90bb-bf0674736661
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 6eb0eeee-5cd2-4e19-8308-4f78f7b794ac
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 99f59949-cace-4b9a-8bf7-98569f8ba701
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 0cc8b83a-a7d6-4cbe-8cc2-01c98d66490e
    `overdraft_amount_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column overdraft_amount_derived',
    -- column_id: e5805afe-ae79-4c03-80e8-9677f4ef57e6
    `balance_end_date_derived` DATE NULL COMMENT 'Fineract source column balance_end_date_derived',
    -- column_id: 1c4db0e2-3edf-4a8b-a362-36a9d9d30ff7
    `balance_number_of_days_derived` INT NULL COMMENT 'Fineract source column balance_number_of_days_derived',
    -- column_id: 75131aa3-b303-4aac-98ad-d424203e64aa
    `running_balance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column running_balance_derived',
    -- column_id: 0bbcddde-c102-427a-9f47-0a0064f056fb
    `cumulative_balance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column cumulative_balance_derived',
    -- column_id: 5b068a7d-e6e5-4e3b-b9cb-059bcb030503
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 04cbcaae-bc80-498b-a8e6-539890dab37d
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: bb1cde38-83f4-4d47-8eea-061ada589540
    `is_manual` BOOLEAN NULL COMMENT 'Fineract source column is_manual',
    -- column_id: 90ed3688-c7f4-44f0-9ddd-298ac1e8dbac
    `release_id_of_hold_amount` BIGINT NULL COMMENT 'Fineract source column release_id_of_hold_amount',
    -- column_id: 3ef49e63-60b7-4db9-ac6d-43d229a33748
    `is_loan_disbursement` BOOLEAN NULL COMMENT 'Fineract source column is_loan_disbursement',
    -- column_id: a9d9f160-88a7-48b6-8071-49c229c339e3
    `ref_no` VARCHAR(128) NULL COMMENT 'Fineract source column ref_no',
    -- column_id: ee17c8fc-f8fb-4705-8cad-93e2a6cdd161
    `original_transaction_id` BIGINT NULL COMMENT 'Fineract source column original_transaction_id',
    -- column_id: fa615a3b-08d3-4711-bfa1-e635f6f63492
    `is_reversal` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversal',
    -- column_id: ab236a33-02d1-458e-85e7-30a5e3711154
    `reason_for_block` VARCHAR(256) NULL COMMENT 'Fineract source column reason_for_block',
    -- column_id: 4e46cc3b-99d8-4034-b34d-cb07dacb5692
    `is_lien_transaction` BOOLEAN NOT NULL COMMENT 'Fineract source column is_lien_transaction',
    -- column_id: bbc42991-9c7e-4e2d-b611-c077be13e060
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 7bc03fc8-98bd-43d0-86e2-acd57258a13c
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 88d12fd1-d845-4565-bd89-689fa5299ba3
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 0f411343-29f9-4b56-95d8-8f5e320946d4
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c91fcadd-f9c9-4c0e-8306-f6449dc6fee6
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 0e283a60-d908-4f7a-8ef2-369b0defe721
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
