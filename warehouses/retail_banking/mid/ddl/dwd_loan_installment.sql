SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_repayment_schedule
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_installment;
-- table_id: b93902f1-b6af-4366-bb81-ff122372db88
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_installment (
    -- column_id: f030e39f-a962-4b5c-9ed8-b56026a318f7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 154988d2-48cc-4140-bc17-218fa8706dcd
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 605d72b5-93ec-4891-bdea-65f063b93cb6
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: a9190b8f-75f0-4d7c-a280-c533e994f20b
    `fromdate` DATE NULL COMMENT 'Fineract source column fromdate',
    -- column_id: 75355994-418b-4d0a-bed1-8a8c38d5a7dd
    `duedate` DATE NOT NULL COMMENT 'Fineract source column duedate',
    -- column_id: 7950fe55-c8b4-48d9-aa3d-22dd79824e65
    `installment` SMALLINT NOT NULL COMMENT 'Fineract source column installment',
    -- column_id: 8bcdcd1e-97f2-42f6-801d-7cd6a75fbffa
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: 85bb29cb-cc57-423a-b86e-dda495c50eb4
    `principal_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_completed_derived',
    -- column_id: 0009e8a8-8692-4d47-b144-33842df82622
    `principal_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_writtenoff_derived',
    -- column_id: 2569fbec-3f48-4367-a171-40c0563cec7a
    `interest_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_amount',
    -- column_id: 0555bc15-d19a-4e8c-87bd-35760535808e
    `interest_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_completed_derived',
    -- column_id: be88acb7-e2b9-4a7f-87dc-af8587da7a25
    `interest_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_writtenoff_derived',
    -- column_id: e5d493fc-ce94-46a4-9066-4dd3b884494f
    `interest_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_waived_derived',
    -- column_id: 2521a8ee-36d8-4b50-a4ed-033fdc050ae6
    `accrual_interest_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column accrual_interest_derived',
    -- column_id: 9912cdef-dc19-4e2c-b1a8-217302c2e39b
    `reschedule_interest_portion` DECIMAL(19,6) NULL COMMENT 'Fineract source column reschedule_interest_portion',
    -- column_id: acf04b5f-2306-458a-aa28-f2be4f7026e6
    `fee_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_amount',
    -- column_id: 5bc79da3-029b-493a-9502-57f76ab00bd7
    `fee_charges_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_completed_derived',
    -- column_id: b883ff60-4137-4fd7-85e7-b77b20ce6ed4
    `fee_charges_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_writtenoff_derived',
    -- column_id: 31bcbc70-3803-463a-a097-fa01c26ac5e5
    `fee_charges_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_waived_derived',
    -- column_id: af8f3e25-924a-4d4c-b50d-b3aba4159dc1
    `accrual_fee_charges_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column accrual_fee_charges_derived',
    -- column_id: 0f8199e6-50b0-4092-a80e-78b104e52c8a
    `penalty_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_amount',
    -- column_id: 6e15ef31-6fda-4355-ad41-b10842ff84b6
    `penalty_charges_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_completed_derived',
    -- column_id: df8ce796-134a-4a99-b47e-7e3d307fcc2e
    `penalty_charges_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_writtenoff_derived',
    -- column_id: 0132065e-bb23-46b7-82f0-30325d40df6e
    `penalty_charges_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_waived_derived',
    -- column_id: 7ec7586b-1adc-4aaf-92e3-a30e232a0c86
    `accrual_penalty_charges_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column accrual_penalty_charges_derived',
    -- column_id: 181fb1a8-6493-4349-8438-51507129f34e
    `total_paid_in_advance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_paid_in_advance_derived',
    -- column_id: 6f18aebf-bb4a-480f-b1de-03bf95465364
    `total_paid_late_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_paid_late_derived',
    -- column_id: bd3f3ba3-5310-48a4-a381-33e2bd90a8b7
    `completed_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column completed_derived',
    -- column_id: cb8e987c-b3bc-4a96-a5e1-41e8f94871d9
    `obligations_met_on_date` DATE NULL COMMENT 'Fineract source column obligations_met_on_date',
    -- column_id: dc4fefe2-a1d9-4edf-afd9-e2cff93e58c9
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 5d4a0438-a443-497b-ace5-d8cdf7d6b30a
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 77e115f9-726e-4448-8089-77497321f8bc
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: af1ef16b-fa61-4146-a0d2-807255bc52df
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: dd5e0b9f-27a0-4dd9-90b4-e55ab5085818
    `recalculated_interest_component` BOOLEAN NOT NULL COMMENT 'Fineract source column recalculated_interest_component',
    -- column_id: 303b8822-da5c-4ea6-8c3d-af6db0d699ae
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 400172d7-bbfb-46de-9878-1c818a526f8f
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: dfa9adbd-a105-4c63-ad19-5baf400b9051
    `is_additional` BOOLEAN NOT NULL COMMENT 'Fineract source column is_additional',
    -- column_id: acce521f-097b-4b04-bc65-c420d40ef2be
    `credits_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column credits_amount',
    -- column_id: 13a26751-6869-4212-84ad-6a1cb7f96290
    `is_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column is_down_payment',
    -- column_id: c8e3f85f-00a5-4a9b-a7fc-263365d83d3c
    `credited_interest` DECIMAL(19,6) NULL COMMENT 'Fineract source column credited_interest',
    -- column_id: 13192d3c-de86-4903-bce8-30b4f23db548
    `credited_fee` DECIMAL(19,6) NULL COMMENT 'Fineract source column credited_fee',
    -- column_id: 03da51b9-caf4-4ea7-9ce8-8f559f7abb2b
    `credited_penalty` DECIMAL(19,6) NULL COMMENT 'Fineract source column credited_penalty',
    -- column_id: 7e643e8f-7e76-4dda-92f3-bc34682487f2
    `is_re_aged` BOOLEAN NOT NULL COMMENT 'Fineract source column is_re_aged',
    -- column_id: 0ee1e385-914c-4e71-9af6-3261160b9453
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
