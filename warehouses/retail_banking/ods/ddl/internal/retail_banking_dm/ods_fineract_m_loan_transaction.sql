-- ODS mirror of Apache Fineract m_loan_transaction (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_transaction;
-- table_id: 88c949f3-1fbf-4de8-bc36-a54c263c1ae8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_transaction (
    -- column_id: 7a991562-d497-412a-9d5f-2b16add1d8e2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 13a15dbb-8251-4a36-a3b1-a5afb87276ad
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 512826b0-a8a1-4e8e-bd81-31c45c279b00
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 950cb4ff-2418-4eeb-abf0-1e7114cea5cb
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: 317d8946-b61a-41f8-9a08-e44b63f3086e
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: cb821183-24b3-4e43-b27e-5e96729f5156
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 93b42bfe-df4b-4c9d-8167-808ece9c84e2
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 34d910e3-5ae4-47ce-bfaa-e290a87bd2d5
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 1073bfc6-3acc-4b82-ab9c-87692be69680
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 673c010b-92c3-4801-a502-c76a30e05651
    `principal_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_portion_derived',
    -- column_id: 97620529-3a2a-44aa-8774-1c1b44be7557
    `interest_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_portion_derived',
    -- column_id: f03242f4-b747-4d57-b0ff-5858ea917e05
    `fee_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_portion_derived',
    -- column_id: 7c9a95fb-8eac-4677-be2b-d8020d293959
    `penalty_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_portion_derived',
    -- column_id: 6b972392-374c-4c7b-8050-71bcd9a940d0
    `overpayment_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column overpayment_portion_derived',
    -- column_id: 1ea48c47-8d61-4dd9-9415-58cf8e08dae5
    `unrecognized_income_portion` DECIMAL(19,6) NULL COMMENT 'Fineract source column unrecognized_income_portion',
    -- column_id: fe11ba35-136a-4a66-9d06-736a817f9035
    `outstanding_loan_balance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column outstanding_loan_balance_derived',
    -- column_id: c54e9167-4ab1-4f28-b604-e252868f0365
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: c6b3b78a-aaac-4285-870b-23521dc1839a
    `manually_adjusted_or_reversed` BOOLEAN NULL COMMENT 'Fineract source column manually_adjusted_or_reversed',
    -- column_id: 54d33d76-c698-4f51-a0a6-8465ef13d80d
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: a0b01058-77d8-477f-9a6e-91e0a5e605aa
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: a5c2b77b-6533-4bfc-9be3-60ac0d1a724f
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 8ee713ba-7405-43c9-9cb7-cf6ab015a2d0
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c16bd42c-42be-42e7-a3ec-72419fe7fee2
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: ea9343d1-2db4-4d82-96eb-8fde0800c754
    `charge_refund_charge_type` VARCHAR(1) NULL COMMENT 'Fineract source column charge_refund_charge_type',
    -- column_id: 1d546bc6-e894-4528-b58d-652fba94fe62
    `reversal_external_id` VARCHAR(100) NULL COMMENT 'Fineract source column reversal_external_id',
    -- column_id: 97aec310-b805-4415-8b05-389b13c23a43
    `reversed_on_date` DATE NULL COMMENT 'Fineract source column reversed_on_date',
    -- column_id: 742e4ceb-b08b-4fcd-84f7-ebfc75c04ee9
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 57647351-97aa-4cfe-97eb-5fb8fa5a0a69
    `classification_cv_id` BIGINT NULL COMMENT 'Fineract source column classification_cv_id',
    -- column_id: 0947e7bc-ac3b-49da-b2bb-4d5e66dd7798
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
