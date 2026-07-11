-- ODS mirror of Apache Fineract m_loan_repayment_schedule (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_repayment_schedule;
-- table_id: 4356cd1b-c05c-448a-9103-31ffd47222d1
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_repayment_schedule (
    -- column_id: 27dab851-628c-42e4-8b43-9a3830fcba00
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c23b297f-8bcb-43b1-ad11-dd7ab3bd50df
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 435877f1-5603-46d1-a390-b9db06786f9a
    `fromdate` DATE NULL COMMENT 'Fineract source column fromdate',
    -- column_id: a9ec9ff8-03f5-4950-a2de-82120560607c
    `duedate` DATE NOT NULL COMMENT 'Fineract source column duedate',
    -- column_id: 36abc52d-85aa-4aba-bd1b-52fea3c0f508
    `installment` SMALLINT NOT NULL COMMENT 'Fineract source column installment',
    -- column_id: f407f569-1e0f-4e79-9976-9c7a2af33d96
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: a9b5d5b5-021e-4e6c-948b-620bc7a9fd34
    `principal_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_completed_derived',
    -- column_id: 600a5c77-b83e-45fa-9664-6f4e5af0bef3
    `principal_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_writtenoff_derived',
    -- column_id: 0eb02441-69b1-4fd7-af69-ed08ffa56968
    `interest_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_amount',
    -- column_id: e22219d7-1778-4e68-ae5d-2c165a6aefe2
    `interest_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_completed_derived',
    -- column_id: 6be6417f-f357-4312-9342-c295eb1303fb
    `interest_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_writtenoff_derived',
    -- column_id: bb51a5ba-88f3-4a96-a193-8039ac0691f2
    `interest_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_waived_derived',
    -- column_id: 277c1c48-533c-4613-8687-7a6e740e900e
    `accrual_interest_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column accrual_interest_derived',
    -- column_id: 08f7eb15-74a9-417f-abc5-d82e75351fad
    `reschedule_interest_portion` DECIMAL(19,6) NULL COMMENT 'Fineract source column reschedule_interest_portion',
    -- column_id: 4175f7f4-a9e7-4edd-8f3f-36a3969a5e0c
    `fee_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_amount',
    -- column_id: 86e87756-da45-4007-9852-66a73db5c7ec
    `fee_charges_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_completed_derived',
    -- column_id: 2b3a3c24-8f48-4064-b423-877c820e5f03
    `fee_charges_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_writtenoff_derived',
    -- column_id: b71683ec-fbc5-4452-baaf-92c13576dfae
    `fee_charges_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_waived_derived',
    -- column_id: 411180f3-65aa-453f-b5b7-9a3403c5a526
    `accrual_fee_charges_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column accrual_fee_charges_derived',
    -- column_id: b49a412d-9e92-4588-ad65-869f88e989aa
    `penalty_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_amount',
    -- column_id: 679ef95b-d3ba-4493-a4f9-e1b262e819cb
    `penalty_charges_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_completed_derived',
    -- column_id: 5ae7076b-8898-4ebc-bd25-28dd11110be3
    `penalty_charges_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_writtenoff_derived',
    -- column_id: 09404b4d-6b13-4acc-88b3-7a103b8a4824
    `penalty_charges_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_waived_derived',
    -- column_id: 7ca0f03f-3e59-4fc0-89df-c935760c016e
    `accrual_penalty_charges_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column accrual_penalty_charges_derived',
    -- column_id: 8db6cdf0-21dd-41e9-aa15-7abc991823a8
    `total_paid_in_advance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_paid_in_advance_derived',
    -- column_id: 0a03e4b7-e378-4319-8a9a-a282c03fd551
    `total_paid_late_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_paid_late_derived',
    -- column_id: 5b8372b0-82d3-42d7-9f11-eaef3454b263
    `completed_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column completed_derived',
    -- column_id: 5b17a410-49cc-401e-93e8-c1d2f14a9d7c
    `obligations_met_on_date` DATE NULL COMMENT 'Fineract source column obligations_met_on_date',
    -- column_id: 258f5048-7260-4a63-8fb3-2e7099bf2385
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: a3669d61-81a6-49c8-9f6e-6e65f1f70668
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 4733e52e-f636-49b9-aa7d-c4a9d24210f0
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 07f0c216-b46f-4881-b8ed-e13d31a8f286
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: bccdd719-3148-471e-bcf1-35433fc87972
    `recalculated_interest_component` BOOLEAN NOT NULL COMMENT 'Fineract source column recalculated_interest_component',
    -- column_id: 28ee27d1-2d0d-4e8f-9f26-7eed7e7cc740
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: d8c46b97-ebdd-4ddf-81b3-380209ab1b40
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c7964148-69dd-4df7-af23-ccbc15e81822
    `is_additional` BOOLEAN NOT NULL COMMENT 'Fineract source column is_additional',
    -- column_id: 92bdd9df-2e20-4b4d-9d42-b4fb90b3bae3
    `credits_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column credits_amount',
    -- column_id: 1c247e89-ce99-4e4a-9003-d5b872bf3154
    `is_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column is_down_payment',
    -- column_id: 23918941-2b27-42b3-a1d0-ddb78512606d
    `credited_interest` DECIMAL(19,6) NULL COMMENT 'Fineract source column credited_interest',
    -- column_id: 9e9d8a46-6b70-4fcb-aeb8-5979c0812246
    `credited_fee` DECIMAL(19,6) NULL COMMENT 'Fineract source column credited_fee',
    -- column_id: 3fbd3b75-adb3-416d-aa87-03b9c043348b
    `credited_penalty` DECIMAL(19,6) NULL COMMENT 'Fineract source column credited_penalty',
    -- column_id: 9b6076fe-6ca7-4a25-b465-ae8ae2842a28
    `is_re_aged` BOOLEAN NOT NULL COMMENT 'Fineract source column is_re_aged',
    -- column_id: 9ace7841-313d-4d53-803a-03a0e939f31e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
