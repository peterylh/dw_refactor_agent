-- DWD generated from m_loan_transaction
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_transaction;
-- table_id: e4c96479-2c60-4286-9f47-f92f0e3959a9
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_transaction (
    -- column_id: 4a46a3e9-0add-4b89-b911-806b336308b2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0c9e4520-8d0f-4f80-a9ba-46c641c4ea65
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 300d01c1-e3a6-4987-bd75-dc5a8fa77197
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 9e0d50b1-6049-4ba0-a82e-4a3047568926
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: eb65aac5-a4d1-4b07-98f5-82c1d28c290f
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 704c1853-480d-4958-83c5-f0a890e1cb4f
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: e4d06090-efbb-413b-8396-7484d7f0ac48
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 896abc8d-fc7d-42d7-ab1a-934d392f9533
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 313dfc8c-4048-4b33-acc4-96456fac7011
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 03c235ae-1c5a-4a23-a34e-f4e42de8c01d
    `principal_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_portion_derived',
    -- column_id: 7ae76594-fd83-4144-b85d-91e44eb0d562
    `interest_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_portion_derived',
    -- column_id: f9867067-e53b-450e-b5e0-4f24ee5c8519
    `fee_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_portion_derived',
    -- column_id: ad69802c-2e11-4d75-9997-494d67f60e76
    `penalty_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_portion_derived',
    -- column_id: aa5dae67-59d8-480a-b089-6a318dc4ffac
    `overpayment_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column overpayment_portion_derived',
    -- column_id: 4da4e4e4-181b-44cb-8cdf-64084c98ba90
    `unrecognized_income_portion` DECIMAL(19,6) NULL COMMENT 'Fineract source column unrecognized_income_portion',
    -- column_id: b16b050f-0afd-49d7-b619-ec7b683fcbbe
    `outstanding_loan_balance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column outstanding_loan_balance_derived',
    -- column_id: e858b0ed-a6df-4f16-8b5b-38444daf4b3c
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 3dd6401b-e0eb-45c1-92ca-4025a64df5c2
    `manually_adjusted_or_reversed` BOOLEAN NULL COMMENT 'Fineract source column manually_adjusted_or_reversed',
    -- column_id: d8ec5936-b17a-4cc4-ba59-b2520342b5b3
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: b007d586-734b-464f-9066-076094701d83
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 4706b133-f41e-4f97-ba2d-24c2236d9b42
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: d27d5351-641c-40d9-8fc5-4978dd10283e
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: fd98a896-dd0a-438a-9429-cb703c884705
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 0cd99b57-fa40-4cd5-b9b5-6c3715825441
    `charge_refund_charge_type` VARCHAR(1) NULL COMMENT 'Fineract source column charge_refund_charge_type',
    -- column_id: 27cc8246-5df7-442b-8bfd-15baa239359c
    `reversal_external_id` VARCHAR(64) NULL COMMENT 'Fineract source column reversal_external_id',
    -- column_id: 211f27c9-4466-4993-9a48-7df9f73d40e5
    `reversed_on_date` DATE NULL COMMENT 'Fineract source column reversed_on_date',
    -- column_id: a9d9ba21-a77f-49ed-9035-f3aeae96cf38
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: f7baa8f2-01d4-4094-b0a3-bdd12e9169a1
    `classification_cv_id` BIGINT NULL COMMENT 'Fineract source column classification_cv_id',
    -- column_id: 75dbd5a0-66eb-4b12-aa72-ff450537654b
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 5300a88e-02e8-499e-8607-4261921942f6
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
