-- DWD account snapshot generated from m_loan
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_account_daily_snapshot;
-- table_id: a2dad3e7-bfc9-4cdf-9bed-253518bdb783
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_account_daily_snapshot (
    -- column_id: 23ed486c-1c23-42b0-9768-d8e4b649d296
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: fa0ac354-c714-4100-8093-8226d741f5b6
    `snapshot_date` DATE NOT NULL COMMENT 'Warehouse account snapshot date',
    -- column_id: 1b7490fb-d770-4220-98de-67063a85ccd6
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: e1cc57db-7ed0-4479-b54e-a9395da46e35
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 4c034d08-acbe-4c48-82a1-29587503e89b
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 7113e749-9e1e-4c33-9460-058dff31faa3
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: b1ca50c4-589f-4393-b1e8-c08e894d363f
    `glim_id` BIGINT NULL COMMENT 'Fineract source column glim_id',
    -- column_id: 8166019e-fde4-4a0a-a50c-69f6baec4f93
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 42f6334f-3871-4e11-9daa-f37b24446a17
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: d8588220-7f21-4cd9-8241-68a4dcd6ac6d
    `loan_officer_id` BIGINT NULL COMMENT 'Fineract source column loan_officer_id',
    -- column_id: fb8ff653-41d1-4b79-beef-21a491cc2572
    `loanpurpose_cv_id` INT NULL COMMENT 'Fineract source column loanpurpose_cv_id',
    -- column_id: 59c73909-3bd5-4972-851d-416b90d84d93
    `loan_status_id` SMALLINT NOT NULL COMMENT 'Fineract source column loan_status_id',
    -- column_id: 60f0d786-76a5-4957-9dfb-af608e3a4d41
    `loan_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column loan_type_enum',
    -- column_id: d90bd818-76a6-4076-b914-55cdc4cc91b5
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: f3c195a9-0a36-4122-8542-a8565797a758
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 11307286-a8c4-480e-bf6f-bc8ea47076af
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 97574d94-89a5-4e35-969d-f2a1fad7dc14
    `principal_amount_proposed` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount_proposed',
    -- column_id: 6208d9f2-eb0d-4b97-a4b4-6d2cc6e8e029
    `principal_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: 7fe5e336-017b-42da-ab72-cf108ec526c4
    `approved_principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column approved_principal',
    -- column_id: 7a713123-d28b-4401-b9f3-009f8c2b2a27
    `net_disbursal_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column net_disbursal_amount',
    -- column_id: 6591c15b-fdc0-4bbf-9a54-631db9df2e5a
    `arrearstolerance_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column arrearstolerance_amount',
    -- column_id: f7b16a0a-cbce-4a7a-b8ca-577c69e88a51
    `is_floating_interest_rate` BOOLEAN NULL COMMENT 'Fineract source column is_floating_interest_rate',
    -- column_id: aabbda51-7a68-42b3-8819-a3e0a273d76f
    `interest_rate_differential` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_rate_differential',
    -- column_id: f0b13082-cd05-413e-8339-e6bcfcf4ebd9
    `nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_interest_rate_per_period',
    -- column_id: 6004a099-39b5-4ac8-a54a-ae5d056344eb
    `interest_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column interest_period_frequency_enum',
    -- column_id: 3e387024-f935-4402-9a8a-cd48bac8dadd
    `annual_nominal_interest_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column annual_nominal_interest_rate',
    -- column_id: 914228ce-4e07-47b0-a4e7-a2817f6e890a
    `interest_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_method_enum',
    -- column_id: e3e6d11c-3951-4c85-884d-0a5db029edaa
    `interest_calculated_in_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculated_in_period_enum',
    -- column_id: 007eafcb-ae53-43a5-9231-3da028b1d17e
    `allow_partial_period_interest_calcualtion` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_partial_period_interest_calcualtion',
    -- column_id: 6d9f55bd-b35f-481b-b994-d1a68009a0e8
    `term_frequency` SMALLINT NOT NULL COMMENT 'Fineract source column term_frequency',
    -- column_id: d10a93cc-b30e-4732-b9bc-152b544b5256
    `term_period_frequency_enum` SMALLINT NOT NULL COMMENT 'Fineract source column term_period_frequency_enum',
    -- column_id: e9f557a7-e38c-476e-a93e-d91e2e5cca1f
    `repay_every` SMALLINT NOT NULL COMMENT 'Fineract source column repay_every',
    -- column_id: 8ebfd96a-aaed-431e-a55b-f9d75f69b21d
    `repayment_period_frequency_enum` SMALLINT NOT NULL COMMENT 'Fineract source column repayment_period_frequency_enum',
    -- column_id: e9848ef3-0143-458d-9155-99a8b3717f1d
    `number_of_repayments` SMALLINT NOT NULL COMMENT 'Fineract source column number_of_repayments',
    -- column_id: 1cccd721-c125-4035-8f1e-820bd8cb46fb
    `grace_on_principal_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_principal_periods',
    -- column_id: 0eee0f06-d9eb-4039-ad4d-86764687346b
    `recurring_moratorium_principal_periods` SMALLINT NULL COMMENT 'Fineract source column recurring_moratorium_principal_periods',
    -- column_id: ba923a5f-fb6f-4bc4-9444-fdc7ae3078c8
    `grace_on_interest_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_interest_periods',
    -- column_id: a6facf28-486a-4e0a-94d0-99a3923e780e
    `grace_interest_free_periods` SMALLINT NULL COMMENT 'Fineract source column grace_interest_free_periods',
    -- column_id: cde79c59-1b1f-460a-985d-7763b7e16d7c
    `amortization_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column amortization_method_enum',
    -- column_id: b0d59794-b70e-4b0a-8e3b-47d567eb1abd
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: e44a90e9-a148-4f0d-8b3a-53c4b5685de5
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: 9ae2ef90-db7a-47e0-a781-66bc0cc310e9
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: d629a4ac-c1fa-441d-91cc-6f6100b2675f
    `expected_disbursedon_date` DATE NULL COMMENT 'Fineract source column expected_disbursedon_date',
    -- column_id: 8f8a197f-c33d-4b0a-a50a-fd3b688d2065
    `expected_firstrepaymenton_date` DATE NULL COMMENT 'Fineract source column expected_firstrepaymenton_date',
    -- column_id: 3e1cd620-3d72-4e40-9ed0-600a11031e1a
    `interest_calculated_from_date` DATE NULL COMMENT 'Fineract source column interest_calculated_from_date',
    -- column_id: fdb7d9ed-fc7e-4a4e-8b1b-693e559d4722
    `disbursedon_date` DATE NULL COMMENT 'Fineract source column disbursedon_date',
    -- column_id: 027ea6a7-f02e-4aa1-bbc6-9ee91a94ae09
    `disbursedon_userid` BIGINT NULL COMMENT 'Fineract source column disbursedon_userid',
    -- column_id: 5c3eb615-952c-4d2e-9c2e-f58e68e08fa4
    `expected_maturedon_date` DATE NULL COMMENT 'Fineract source column expected_maturedon_date',
    -- column_id: fe95a335-47c0-4994-b455-dc95ecd76e55
    `maturedon_date` DATE NULL COMMENT 'Fineract source column maturedon_date',
    -- column_id: d77fe406-958c-4118-abba-8623332c846e
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: bc5afea1-7f74-4e96-b85d-868a2d18b007
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 55e025f7-acb2-4451-9159-a82118e7edab
    `total_charges_due_at_disbursement_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_charges_due_at_disbursement_derived',
    -- column_id: f4c150af-07f1-44d6-ae9b-bda8c03c4b64
    `principal_disbursed_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_disbursed_derived',
    -- column_id: 92e7da67-9098-4938-bc5a-d52c497f0ddb
    `principal_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_repaid_derived',
    -- column_id: da8c2a6d-f2c9-4611-bd35-a14b42dd2e3c
    `principal_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_writtenoff_derived',
    -- column_id: 50a1e1b5-6c1e-45e5-85bc-a664bfe7f76e
    `principal_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_outstanding_derived',
    -- column_id: f9844445-afc7-4dd1-b018-c6dab2ad872b
    `interest_charged_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_charged_derived',
    -- column_id: d22ae502-b18a-43a5-9654-5cdb959db190
    `interest_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_repaid_derived',
    -- column_id: 1dbc1353-8006-4f5b-bc6b-2395640c2f8b
    `interest_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_waived_derived',
    -- column_id: b7472aaa-24f9-4c6d-ab67-adaf8e9b5539
    `interest_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_writtenoff_derived',
    -- column_id: da87c5b5-004f-4f62-bbfa-9b2aaf0e58ed
    `interest_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_outstanding_derived',
    -- column_id: edafdccd-c31e-43e6-ae96-80a574d24a77
    `fee_charges_charged_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_charged_derived',
    -- column_id: ff1e32f9-ea53-4c49-b548-2d4e8cf132a2
    `fee_charges_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_repaid_derived',
    -- column_id: c3d2fdd2-d66f-406d-8428-a4584e2b419b
    `fee_charges_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_waived_derived',
    -- column_id: ddc08fbc-d30d-4887-a517-e7b8c861d3f7
    `fee_charges_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_writtenoff_derived',
    -- column_id: 2df0645e-a782-4035-a276-aedbf0536e81
    `fee_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_outstanding_derived',
    -- column_id: 8b29119c-d3f9-48ca-8940-95fc5c74c248
    `penalty_charges_charged_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_charged_derived',
    -- column_id: b30f04a2-d605-4bf1-984d-7a4a51cfecc3
    `penalty_charges_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_repaid_derived',
    -- column_id: c183e063-1cc0-44f8-a3e8-ff795b0f87ca
    `penalty_charges_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_waived_derived',
    -- column_id: 850618fe-7806-42c4-bd4e-15352e6088d4
    `penalty_charges_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_writtenoff_derived',
    -- column_id: 4774d4e7-710a-48da-98d2-33756d5f1962
    `penalty_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_outstanding_derived',
    -- column_id: b81c161d-2097-473c-9874-e5fe234f32e8
    `total_expected_repayment_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_expected_repayment_derived',
    -- column_id: 8eb85ed7-ed50-4c71-87fe-0bd6ea642504
    `total_repayment_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_repayment_derived',
    -- column_id: dcdfcc28-afed-490c-86ea-bd6ed67778d4
    `total_expected_costofloan_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_expected_costofloan_derived',
    -- column_id: b4cbbbb0-bb71-4265-8780-69acbcc8bd80
    `total_costofloan_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_costofloan_derived',
    -- column_id: 44ff44e8-de99-46dc-a0de-933adcfbd759
    `total_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_waived_derived',
    -- column_id: 42c3daad-f95a-4194-b0a5-e770433e98bb
    `total_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_writtenoff_derived',
    -- column_id: 174fcee7-41f7-4f15-8579-de3dda918056
    `total_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_outstanding_derived',
    -- column_id: ada8b745-4b58-45ac-82d4-99fad8e80500
    `total_overpaid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_overpaid_derived',
    -- column_id: 011eeb5b-923c-4dc5-82ca-b47717a9ee7a
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: 05e0ad56-c0d7-4a1d-a0fb-142d04169750
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: 35699ccd-77ff-4e49-ac21-17b6efb988e2
    `rescheduledon_date` DATE NULL COMMENT 'Fineract source column rescheduledon_date',
    -- column_id: 3c8843b3-2716-40df-a4af-1acbcb7ed088
    `rescheduledon_userid` BIGINT NULL COMMENT 'Fineract source column rescheduledon_userid',
    -- column_id: 28059287-311b-4a88-89aa-9b618d7e2b73
    `withdrawnon_date` DATE NULL COMMENT 'Fineract source column withdrawnon_date',
    -- column_id: ce4ede9e-b6e4-4243-be67-8fe1b7f8b46f
    `withdrawnon_userid` BIGINT NULL COMMENT 'Fineract source column withdrawnon_userid',
    -- column_id: e7497fa4-f4a2-41e6-bd87-3b0411af0a30
    `writtenoffon_date` DATE NULL COMMENT 'Fineract source column writtenoffon_date',
    -- column_id: f035d4a2-1239-46ea-bf2b-db7b0cf666f3
    `loan_transaction_strategy_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_strategy_id',
    -- column_id: 43c63fc8-b683-43e0-bf23-0daa28c70395
    `sync_disbursement_with_meeting` BOOLEAN NULL COMMENT 'Fineract source column sync_disbursement_with_meeting',
    -- column_id: 2b5ce60f-0748-4fa1-8a63-435618ca25a4
    `loan_counter` SMALLINT NULL COMMENT 'Fineract source column loan_counter',
    -- column_id: 10efd9f2-1b89-4ed1-9cd1-5a2284898999
    `loan_product_counter` SMALLINT NULL COMMENT 'Fineract source column loan_product_counter',
    -- column_id: 51e89490-5b01-4838-8ade-41b4b92c06de
    `fixed_emi_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column fixed_emi_amount',
    -- column_id: a9403829-ae95-475a-a981-b6f12b0962a8
    `max_outstanding_loan_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_outstanding_loan_balance',
    -- column_id: e516a23d-f67b-49b4-ac77-b67e85da161b
    `grace_on_arrears_ageing` SMALLINT NULL COMMENT 'Fineract source column grace_on_arrears_ageing',
    -- column_id: 438800ff-d2dd-4a4f-a6fd-6649ed5dc24f
    `is_npa` BOOLEAN NOT NULL COMMENT 'Fineract source column is_npa',
    -- column_id: 9695dcf2-4aa8-45b0-9c05-7233569940fb
    `total_recovered_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_recovered_derived',
    -- column_id: 66fcf03f-5b21-476d-a516-c954abe9112e
    `accrued_till` DATE NULL COMMENT 'Fineract source column accrued_till',
    -- column_id: 1b1443d7-cca6-41e3-8f01-1c1f1db91f89
    `interest_recalcualated_on` DATE NULL COMMENT 'Fineract source column interest_recalcualated_on',
    -- column_id: 0f69073d-2f7d-4ba4-a634-cd8c9e1e64f3
    `days_in_month_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_month_enum',
    -- column_id: 28c13e9b-7cc9-497a-9da5-45c5742d9f16
    `days_in_year_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_year_enum',
    -- column_id: 0d35f66b-d0fd-4e45-8692-34eedb71d02f
    `interest_recalculation_enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recalculation_enabled',
    -- column_id: 6a9e7cf9-0756-4fd1-9d94-c290b8bedbbc
    `guarantee_amount_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column guarantee_amount_derived',
    -- column_id: b9ae43f6-bf5a-491a-838d-6a4a3611edc1
    `create_standing_instruction_at_disbursement` BOOLEAN NULL COMMENT 'Fineract source column create_standing_instruction_at_disbursement',
    -- column_id: f524f51e-34f6-4708-adf0-05aff2590ec0
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: d85cbb5f-afca-4829-a683-e263af876d45
    `writeoff_reason_cv_id` INT NULL COMMENT 'Fineract source column writeoff_reason_cv_id',
    -- column_id: 6b2d5897-ce3b-4de5-a033-ec5d184c6676
    `loan_sub_status_id` SMALLINT NULL COMMENT 'Fineract source column loan_sub_status_id',
    -- column_id: 78c9e69f-0820-4796-8ef8-91bf7590a29d
    `is_topup` BOOLEAN NOT NULL COMMENT 'Fineract source column is_topup',
    -- column_id: 006ff8db-73c3-46cf-9c1c-3e14bcee6189
    `is_equal_amortization` BOOLEAN NOT NULL COMMENT 'Fineract source column is_equal_amortization',
    -- column_id: d5bfbfaa-726f-4375-ba97-f84bb35678ef
    `fixed_principal_percentage_per_installment` DECIMAL(5,2) NULL COMMENT 'Fineract source column fixed_principal_percentage_per_installment',
    -- column_id: 68f52529-d912-4008-ad5b-9e0c8e1ed17d
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 5e7c6ae9-6916-4977-bcfc-bcb5152821c5
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 1ae8a545-e700-4474-8867-0cf795b05341
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 6f1a8b7e-0821-40ac-91cf-8fe2c3c85e4e
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 11f5fed1-259c-484c-bac2-886b9c7a228a
    `principal_adjustments_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_adjustments_derived',
    -- column_id: e112f185-b76f-4b04-8642-79552cd4890b
    `is_fraud` BOOLEAN NOT NULL COMMENT 'Fineract source column is_fraud',
    -- column_id: 2b57de78-f632-4be7-94ae-8a05d1a0c396
    `loan_transaction_strategy_code` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_code',
    -- column_id: 3c661de7-23e2-4e64-b464-25747c515128
    `loan_transaction_strategy_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_name',
    -- column_id: 3f165035-2600-4287-85ff-c75c0a177ab4
    `last_closed_business_date` DATE NULL COMMENT 'Fineract source column last_closed_business_date',
    -- column_id: 1c756710-0d3e-49c8-bffc-ebe9832df2e9
    `overpaidon_date` DATE NULL COMMENT 'Fineract source column overpaidon_date',
    -- column_id: 848c53ab-ac02-4fc3-ab3b-119d375d1f9a
    `is_charged_off` BOOLEAN NOT NULL COMMENT 'Fineract source column is_charged_off',
    -- column_id: bafe1df4-440a-4286-9d6a-be2ffbe02804
    `charged_off_on_date` DATE NULL COMMENT 'Fineract source column charged_off_on_date',
    -- column_id: cd1cb47f-bee9-4edb-996a-59982c34b325
    `charge_off_reason_cv_id` BIGINT NULL COMMENT 'Fineract source column charge_off_reason_cv_id',
    -- column_id: b7b92e3d-0347-45c0-8bf2-53501c1f45b2
    `charged_off_by_userid` BIGINT NULL COMMENT 'Fineract source column charged_off_by_userid',
    -- column_id: 904f4d57-b66e-41a1-8fc6-94a29f2f726f
    `enable_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_down_payment',
    -- column_id: e590f84b-0e60-4949-8bb4-284973558039
    `disbursed_amount_percentage_for_down_payment` DECIMAL(9,6) NULL COMMENT 'Fineract source column disbursed_amount_percentage_for_down_payment',
    -- column_id: bf9b621a-4b0c-4d58-bb7b-d5f8088a60dc
    `enable_installment_level_delinquency` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_installment_level_delinquency',
    -- column_id: 9800b1eb-9f5b-4033-9503-a1d67cc7965c
    `enable_accrual_activity_posting` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_accrual_activity_posting',
    -- column_id: c17cb8dd-5368-4e0c-925c-d37b8826bd2a
    `days_in_year_custom_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column days_in_year_custom_strategy',
    -- column_id: 234cb74c-e8d9-4a6b-87d0-28ea4681187d
    `enable_income_capitalization` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_income_capitalization',
    -- column_id: ee8d2ffe-7251-4c80-84d4-f7ad30b853c0
    `capitalized_income_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_calculation_type',
    -- column_id: e4135635-4520-4ad0-b342-d064705695db
    `capitalized_income_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_strategy',
    -- column_id: 8bca7d8c-a627-4d6f-9c65-beca59e090c7
    `capitalized_income_type` VARCHAR(10) NULL COMMENT 'Fineract source column capitalized_income_type',
    -- column_id: 9733d9e4-a4bd-45a0-a1fc-8910fa9361fd
    `capitalized_income_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column capitalized_income_derived',
    -- column_id: d92ccf58-183e-42cf-b766-99dfc5772b52
    `capitalized_income_adjustment_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column capitalized_income_adjustment_derived',
    -- column_id: 7074ea27-3ed8-4676-9828-37a17ed1b1ec
    `total_principal_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_principal_derived',
    -- column_id: 7a9dfa8e-33ef-4189-b9fd-37b6b44a11a4
    `enable_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_buy_down_fee',
    -- column_id: 35c090e5-9529-435a-88fd-99d2744c7b6d
    `buy_down_fee_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_calculation_type',
    -- column_id: ae3367e2-eb8e-4e19-b672-d0f5d25c1b68
    `buy_down_fee_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_strategy',
    -- column_id: ecde2efc-1482-4485-bfc3-0bfdcead2347
    `buy_down_fee_income_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_income_type',
    -- column_id: a16b2008-cdf4-410e-a7f9-a8deb89d0150
    `allow_full_term_for_tranche` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_full_term_for_tranche',
    -- column_id: 1c1da59a-c92e-40ab-afec-3f8c1119e436
    `repayment_start_date_type_enum` SMALLINT NULL COMMENT 'Fineract source column repayment_start_date_type_enum',
    -- column_id: 2ad34677-b54a-4ea2-a08a-ebe5b6f885b7
    `enable_auto_repayment_for_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_auto_repayment_for_down_payment',
    -- column_id: c8fd0b25-027e-4b20-8ff3-6dfc4b30008f
    `loan_schedule_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_type',
    -- column_id: 574b711d-e07b-4cc6-9e96-5db414d265ea
    `loan_schedule_processing_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_processing_type',
    -- column_id: c4b5570b-e8e1-4e77-a2c5-786fbb289505
    `fee_adjustments_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_adjustments_derived',
    -- column_id: 62688240-7bd3-4091-930b-c1dec6f0121c
    `penalty_adjustments_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_adjustments_derived',
    -- column_id: 87f88c5c-0aec-4fce-8266-ad0752e17142
    `fixed_length` SMALLINT NULL COMMENT 'Fineract source column fixed_length',
    -- column_id: 66fc7eae-d344-47b5-b2f5-72c0bfe7dbb9
    `supported_interest_refund_types` STRING NULL COMMENT 'Fineract source column supported_interest_refund_types',
    -- column_id: 64a2d75d-7f5e-4673-b40d-52e48ae31242
    `charge_off_behaviour` VARCHAR(20) NULL COMMENT 'Fineract source column charge_off_behaviour',
    -- column_id: 51aa033d-8da1-4e48-bd46-233221d52a56
    `interest_recognition_on_disbursement_date` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recognition_on_disbursement_date',
    -- column_id: a9b804f4-d868-4de5-9394-b9fd27d44237
    `installment_amount_in_multiples_of` DECIMAL(19,6) NULL COMMENT 'Fineract source column installment_amount_in_multiples_of',
    -- column_id: e66fafcb-8a8e-4b7c-8d4a-ab89421592ef
    `is_merchant_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column is_merchant_buy_down_fee',
    -- column_id: 8288d0b5-dd82-4f9b-b286-e038347c68a9
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `snapshot_date`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
