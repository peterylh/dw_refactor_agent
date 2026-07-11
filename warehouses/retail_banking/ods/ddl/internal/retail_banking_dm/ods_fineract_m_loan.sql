-- ODS mirror of Apache Fineract m_loan (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan;
-- table_id: df7e0ae5-5561-43e5-9cad-723760747973
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan (
    -- column_id: 1d2523bf-400f-44f2-a58d-23896844dfe3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 36ed465d-ec20-47f1-9a47-deee426b891a
    `account_no` VARCHAR(20) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 585b4e97-6760-4f6e-a64b-89e43f455414
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 4e5eea3d-d857-4714-b68d-069871e91709
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 1ba14205-0ded-4d4e-b599-b5c7cbfb4590
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: e55473fe-3874-4858-b409-144ee6185972
    `glim_id` BIGINT NULL COMMENT 'Fineract source column glim_id',
    -- column_id: 2905e880-c3ac-4117-91b6-4f2604424099
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 7861db81-bdea-49da-a491-e60790694621
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: 1e82e953-5968-4341-a16e-4712d9062413
    `loan_officer_id` BIGINT NULL COMMENT 'Fineract source column loan_officer_id',
    -- column_id: 4648a635-e65d-4692-9395-c7ae806fedd2
    `loanpurpose_cv_id` INT NULL COMMENT 'Fineract source column loanpurpose_cv_id',
    -- column_id: 6d4f5306-f59f-4e52-830a-f27bb835dc28
    `loan_status_id` SMALLINT NOT NULL COMMENT 'Fineract source column loan_status_id',
    -- column_id: 9c2be70d-9fe7-42f3-bd80-092b8a190629
    `loan_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column loan_type_enum',
    -- column_id: 3b916754-d8a5-4131-9ebb-0d32f3fb75e2
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 788faeac-ff15-494a-8b3f-ba90160e5f43
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: f0d3290b-f6f9-4731-8141-98b159c80cf1
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: ce69b541-009b-4613-a74d-3f6db58c82a4
    `principal_amount_proposed` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount_proposed',
    -- column_id: 88108f95-1a0c-4650-af90-d0633ff8b3f2
    `principal_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: a74200d1-9974-4097-8b1c-f6d7c6b7cc31
    `approved_principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column approved_principal',
    -- column_id: 681c92c6-bfca-45f8-8235-ee97b3a110c7
    `net_disbursal_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column net_disbursal_amount',
    -- column_id: dc6f41c0-d093-41c8-947f-653aa1a870f9
    `arrearstolerance_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column arrearstolerance_amount',
    -- column_id: 1e9d86e9-1a28-4412-955c-bde650e65498
    `is_floating_interest_rate` BOOLEAN NULL COMMENT 'Fineract source column is_floating_interest_rate',
    -- column_id: a67e1bd4-2174-4fa5-ad2b-d8c5c1eadfdd
    `interest_rate_differential` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_rate_differential',
    -- column_id: 9ee62d0a-13a7-42da-940c-c5c58c164ca2
    `nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_interest_rate_per_period',
    -- column_id: 04550dc7-2e72-444c-84af-cae567332675
    `interest_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column interest_period_frequency_enum',
    -- column_id: dbb10c77-e3da-4f2e-a9bf-5404b3bbc730
    `annual_nominal_interest_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column annual_nominal_interest_rate',
    -- column_id: b5d4b772-07b5-4861-8981-5156762010ad
    `interest_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_method_enum',
    -- column_id: 3fc336fb-5b2f-4c09-a9ab-c4b51deb1de7
    `interest_calculated_in_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculated_in_period_enum',
    -- column_id: 3a632ad7-f155-4d77-af50-16b948ec4b83
    `allow_partial_period_interest_calcualtion` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_partial_period_interest_calcualtion',
    -- column_id: 5df001b8-0f21-4b7f-b9d4-63cec5b33ca3
    `term_frequency` SMALLINT NOT NULL COMMENT 'Fineract source column term_frequency',
    -- column_id: bd0c8030-53ae-4db4-83d8-aecd916bbd96
    `term_period_frequency_enum` SMALLINT NOT NULL COMMENT 'Fineract source column term_period_frequency_enum',
    -- column_id: 279f9ee7-cac4-4513-bebe-adc6448a8d2c
    `repay_every` SMALLINT NOT NULL COMMENT 'Fineract source column repay_every',
    -- column_id: a8672c43-5e28-4549-adc3-2f38a5403408
    `repayment_period_frequency_enum` SMALLINT NOT NULL COMMENT 'Fineract source column repayment_period_frequency_enum',
    -- column_id: 14a59ef1-8994-4f9b-8936-1857839bf6e1
    `number_of_repayments` SMALLINT NOT NULL COMMENT 'Fineract source column number_of_repayments',
    -- column_id: 54e63ff5-ffed-4ce8-89e4-6ec7d5f977b7
    `grace_on_principal_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_principal_periods',
    -- column_id: 6a457c24-1228-40cb-a3ba-133631500319
    `recurring_moratorium_principal_periods` SMALLINT NULL COMMENT 'Fineract source column recurring_moratorium_principal_periods',
    -- column_id: 71b04dd7-1655-470e-9377-b0098e2f4018
    `grace_on_interest_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_interest_periods',
    -- column_id: 933696bc-8884-4cd2-8fe8-0201ee173342
    `grace_interest_free_periods` SMALLINT NULL COMMENT 'Fineract source column grace_interest_free_periods',
    -- column_id: fb85c2d5-68cd-41ed-ae3f-9d8aa41343b9
    `amortization_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column amortization_method_enum',
    -- column_id: 0ca18fa2-a266-4b6a-8dd9-32446f1d545d
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: d34cd88f-d952-45cd-a1c1-7aaba53f41eb
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: b7c6aebf-221c-4b46-878c-dac54d99d6d4
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: 64a691fb-cd8c-4c41-8ef6-9547be293a35
    `expected_disbursedon_date` DATE NULL COMMENT 'Fineract source column expected_disbursedon_date',
    -- column_id: e684d70d-1e1a-4df6-a841-9f4937dd7430
    `expected_firstrepaymenton_date` DATE NULL COMMENT 'Fineract source column expected_firstrepaymenton_date',
    -- column_id: fa36bf70-4d74-4e64-9071-02f62fad392a
    `interest_calculated_from_date` DATE NULL COMMENT 'Fineract source column interest_calculated_from_date',
    -- column_id: df03c90d-7e73-4c62-8c13-b6db0298c43c
    `disbursedon_date` DATE NULL COMMENT 'Fineract source column disbursedon_date',
    -- column_id: 17d5075f-8331-4703-ac37-6b3f242b81ac
    `disbursedon_userid` BIGINT NULL COMMENT 'Fineract source column disbursedon_userid',
    -- column_id: 5c5aa505-37ff-4c61-b307-964bfc454995
    `expected_maturedon_date` DATE NULL COMMENT 'Fineract source column expected_maturedon_date',
    -- column_id: 76f6441d-1cb9-4df5-aff2-23e5c60965c1
    `maturedon_date` DATE NULL COMMENT 'Fineract source column maturedon_date',
    -- column_id: 523fee13-3309-4f3b-96c9-c9e9803a854b
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: b073fc44-f5a9-4f6c-930e-06e4a1300a96
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: adcbc73d-253d-449c-b90a-05ff2b793003
    `total_charges_due_at_disbursement_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_charges_due_at_disbursement_derived',
    -- column_id: c83c7972-ad21-4009-842c-d49d816571ed
    `principal_disbursed_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_disbursed_derived',
    -- column_id: 98a87fe1-bdfe-494f-b9c3-2df89301e6d8
    `principal_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_repaid_derived',
    -- column_id: 20f4dfcf-a25a-49e5-9dc9-8356a8b2fd26
    `principal_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_writtenoff_derived',
    -- column_id: d05d74d6-69d0-4aa5-90ca-1d648f1fb9c0
    `principal_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_outstanding_derived',
    -- column_id: 635d922d-8a88-43ba-bee4-f05106cf6587
    `interest_charged_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_charged_derived',
    -- column_id: 68965de7-abe0-446c-83df-48a55590e4de
    `interest_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_repaid_derived',
    -- column_id: a08a39e5-f4b0-4094-befa-47826308186c
    `interest_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_waived_derived',
    -- column_id: af479e33-8df4-4785-8390-a8ee403fb0dc
    `interest_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_writtenoff_derived',
    -- column_id: 1f71402d-3508-4189-8149-e67cbb9762e7
    `interest_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_outstanding_derived',
    -- column_id: 2a7f3d5c-e1b5-483f-8974-97de1d884632
    `fee_charges_charged_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_charged_derived',
    -- column_id: 0cd8ea1a-1c73-4c73-8932-f68eb43c6399
    `fee_charges_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_repaid_derived',
    -- column_id: 0edc0f59-797f-4a55-b3d7-7993f10e9888
    `fee_charges_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_waived_derived',
    -- column_id: df9ade4c-9636-4bd0-8275-ab20af86d003
    `fee_charges_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_writtenoff_derived',
    -- column_id: 815aba02-0ac0-4e48-b079-66f3c67463a4
    `fee_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_outstanding_derived',
    -- column_id: 7cadba88-d7e1-4c1f-ac03-7e63665b3a9e
    `penalty_charges_charged_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_charged_derived',
    -- column_id: 5ea2d08f-6277-463a-97ef-f56c274ac32b
    `penalty_charges_repaid_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_repaid_derived',
    -- column_id: 5af258b8-5fad-4e23-a595-8f9a81d95bae
    `penalty_charges_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_waived_derived',
    -- column_id: 5d20d36e-af47-468d-93ac-2270a5d50524
    `penalty_charges_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_writtenoff_derived',
    -- column_id: 08539d01-ae53-474f-b6ac-0e47e2580ffc
    `penalty_charges_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_outstanding_derived',
    -- column_id: 041a9b83-5109-45b6-812f-af1cf3763bc1
    `total_expected_repayment_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_expected_repayment_derived',
    -- column_id: 9f9167ce-00c8-487a-9f40-c41b57847090
    `total_repayment_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_repayment_derived',
    -- column_id: b306adfd-0bd6-4cf2-9517-536ffe8f05f9
    `total_expected_costofloan_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_expected_costofloan_derived',
    -- column_id: 2258f6ca-6400-43e8-87bb-d348f21c4647
    `total_costofloan_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_costofloan_derived',
    -- column_id: d7171b5a-62b3-4931-ba39-5e8771d41102
    `total_waived_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_waived_derived',
    -- column_id: 111f0f7b-5a4f-4430-b004-2cba7cbf25b5
    `total_writtenoff_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_writtenoff_derived',
    -- column_id: 98774c0f-8140-4161-be33-643460acc3dd
    `total_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_outstanding_derived',
    -- column_id: 611d22d7-a805-4017-9f13-8625520ac1f4
    `total_overpaid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_overpaid_derived',
    -- column_id: 095e66a2-5cc7-4ca4-8e11-049147eb6ba2
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: 45e7b84b-dd94-4f0d-8862-344f7f4af9b7
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: 9d2907cd-7ca7-4b27-89c2-ce98b368e5bd
    `rescheduledon_date` DATE NULL COMMENT 'Fineract source column rescheduledon_date',
    -- column_id: 201fcd54-2586-47a0-95e0-c13ce097c06d
    `rescheduledon_userid` BIGINT NULL COMMENT 'Fineract source column rescheduledon_userid',
    -- column_id: 9e62ea1f-66fd-4529-8535-c5e6f8e8f7f5
    `withdrawnon_date` DATE NULL COMMENT 'Fineract source column withdrawnon_date',
    -- column_id: 1dbc5d43-ee4f-4ccf-9474-202e81cc0a33
    `withdrawnon_userid` BIGINT NULL COMMENT 'Fineract source column withdrawnon_userid',
    -- column_id: 070c6ff1-a5ca-4ca2-a50a-f99c81050cef
    `writtenoffon_date` DATE NULL COMMENT 'Fineract source column writtenoffon_date',
    -- column_id: 33e061ef-597f-4010-93d5-5b65f916e99d
    `loan_transaction_strategy_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_strategy_id',
    -- column_id: d560b656-698e-4cf4-b62e-afa50f428959
    `sync_disbursement_with_meeting` BOOLEAN NULL COMMENT 'Fineract source column sync_disbursement_with_meeting',
    -- column_id: d2ba3e34-0f9b-4838-8ac8-18c5118b7d4d
    `loan_counter` SMALLINT NULL COMMENT 'Fineract source column loan_counter',
    -- column_id: d8859076-91fa-40b0-a4f6-c9ea65ffca40
    `loan_product_counter` SMALLINT NULL COMMENT 'Fineract source column loan_product_counter',
    -- column_id: 3c9016d2-7d62-4b9a-af29-bfa1706f8a3b
    `fixed_emi_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column fixed_emi_amount',
    -- column_id: ac0871c7-c664-48df-91ea-1be241658607
    `max_outstanding_loan_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_outstanding_loan_balance',
    -- column_id: b0aed787-56a5-4b9e-bb45-b47c26b58869
    `grace_on_arrears_ageing` SMALLINT NULL COMMENT 'Fineract source column grace_on_arrears_ageing',
    -- column_id: 374d3b6f-deb5-444a-9dd6-4d36a4e83528
    `is_npa` BOOLEAN NOT NULL COMMENT 'Fineract source column is_npa',
    -- column_id: ef20da3b-e825-443d-be24-992bf760c369
    `total_recovered_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_recovered_derived',
    -- column_id: f8bf7984-5b69-46bb-a77b-d0448144374d
    `accrued_till` DATE NULL COMMENT 'Fineract source column accrued_till',
    -- column_id: e90e465d-7a59-45f6-a239-908bb3b361a7
    `interest_recalcualated_on` DATE NULL COMMENT 'Fineract source column interest_recalcualated_on',
    -- column_id: 16b89528-11a0-4bee-bb17-3d52358fd624
    `days_in_month_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_month_enum',
    -- column_id: c385b0ea-af4b-46f3-95ad-a495a4ea9ae9
    `days_in_year_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_year_enum',
    -- column_id: 1a7ae344-a3f6-484b-8973-61f6ea5a3947
    `interest_recalculation_enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recalculation_enabled',
    -- column_id: c697818d-ca89-4ec2-a0bd-b276ce49b769
    `guarantee_amount_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column guarantee_amount_derived',
    -- column_id: 85e6563f-6be6-4b49-8381-9fd23a0259e0
    `create_standing_instruction_at_disbursement` BOOLEAN NULL COMMENT 'Fineract source column create_standing_instruction_at_disbursement',
    -- column_id: a262e0bd-3054-4cff-aadc-29c81b094442
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 7a0ee03b-618d-4309-88b6-42578d22febb
    `writeoff_reason_cv_id` INT NULL COMMENT 'Fineract source column writeoff_reason_cv_id',
    -- column_id: aa1e92e5-63a7-4956-881a-f5b460a02177
    `loan_sub_status_id` SMALLINT NULL COMMENT 'Fineract source column loan_sub_status_id',
    -- column_id: 5e5fceea-d0de-4fc3-aa1d-6283599ae2dc
    `is_topup` BOOLEAN NOT NULL COMMENT 'Fineract source column is_topup',
    -- column_id: 2bf944dd-4b5c-409d-93e3-bf47707eae8f
    `is_equal_amortization` BOOLEAN NOT NULL COMMENT 'Fineract source column is_equal_amortization',
    -- column_id: 3de7fa16-15f1-4651-b647-cd0f29114eb7
    `fixed_principal_percentage_per_installment` DECIMAL(5,2) NULL COMMENT 'Fineract source column fixed_principal_percentage_per_installment',
    -- column_id: 5dcd1ddb-19ae-4789-a324-bd247ee54dcf
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 79468971-afd9-419b-9f26-05d615d41ddd
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: c6cf16c5-c27e-490f-9774-35cde4566c4e
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: e4667732-915d-4571-96bb-181ba20855b3
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: d4588484-6ca9-45d7-8ce6-3394133770ef
    `principal_adjustments_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_adjustments_derived',
    -- column_id: 3c4bd715-93c0-4df5-9037-2b71bdde255d
    `is_fraud` BOOLEAN NOT NULL COMMENT 'Fineract source column is_fraud',
    -- column_id: ec965c30-1eb0-42a6-aa20-800e89898a67
    `loan_transaction_strategy_code` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_code',
    -- column_id: e02e3801-cc19-4403-8f3a-bc28c188f5b7
    `loan_transaction_strategy_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_name',
    -- column_id: f2ed9cb5-7f93-4236-98b1-39bd9f36b734
    `last_closed_business_date` DATE NULL COMMENT 'Fineract source column last_closed_business_date',
    -- column_id: 9218fae0-1d06-47fd-8123-60a80d2c965d
    `overpaidon_date` DATE NULL COMMENT 'Fineract source column overpaidon_date',
    -- column_id: 89247fdd-fc48-456b-925b-0e316a919947
    `is_charged_off` BOOLEAN NOT NULL COMMENT 'Fineract source column is_charged_off',
    -- column_id: 9fe07fc9-c01a-4960-91a7-87ba74b253cf
    `charged_off_on_date` DATE NULL COMMENT 'Fineract source column charged_off_on_date',
    -- column_id: f29ed0d7-6137-4699-bce6-eec4a74d008b
    `charge_off_reason_cv_id` BIGINT NULL COMMENT 'Fineract source column charge_off_reason_cv_id',
    -- column_id: 403c35f6-b0fd-4386-ae59-dec2312a4272
    `charged_off_by_userid` BIGINT NULL COMMENT 'Fineract source column charged_off_by_userid',
    -- column_id: 9756686a-609f-499f-9bfc-402decc62dbf
    `enable_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_down_payment',
    -- column_id: 7740c11e-5406-4922-8033-d6b906d600b1
    `disbursed_amount_percentage_for_down_payment` DECIMAL(9,6) NULL COMMENT 'Fineract source column disbursed_amount_percentage_for_down_payment',
    -- column_id: e84eb5e6-9809-4c16-bd3a-0f5f1e8d488a
    `enable_installment_level_delinquency` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_installment_level_delinquency',
    -- column_id: 4d6a8cc3-3d85-405a-bc88-86c00a3cff6f
    `enable_accrual_activity_posting` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_accrual_activity_posting',
    -- column_id: e3268841-391e-4907-a202-b3dbe36f2c52
    `days_in_year_custom_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column days_in_year_custom_strategy',
    -- column_id: 68cbdf0c-9f5a-468e-980d-f47b691dafb9
    `enable_income_capitalization` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_income_capitalization',
    -- column_id: 55d27bbf-2287-4ab2-ba94-3c85fcf8404a
    `capitalized_income_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_calculation_type',
    -- column_id: 536b0ee7-717f-4c3b-ae75-444e2a5f4333
    `capitalized_income_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_strategy',
    -- column_id: 2adac67e-d120-4bb1-9cf7-1e211ff85aa4
    `capitalized_income_type` VARCHAR(10) NULL COMMENT 'Fineract source column capitalized_income_type',
    -- column_id: 8678dd88-2ac8-45f5-b01d-04b44838c941
    `capitalized_income_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column capitalized_income_derived',
    -- column_id: 8da06755-457d-402b-82f1-fa5b1c766099
    `capitalized_income_adjustment_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column capitalized_income_adjustment_derived',
    -- column_id: 36c631fd-3242-4588-88fe-876df49ceca4
    `total_principal_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_principal_derived',
    -- column_id: 30c30ee5-8216-4735-b4a6-9b4399310cd9
    `enable_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_buy_down_fee',
    -- column_id: ece26015-1561-4138-8bd1-464a355538d3
    `buy_down_fee_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_calculation_type',
    -- column_id: 77881cc9-d2e6-43a4-aaee-da48d8de9359
    `buy_down_fee_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_strategy',
    -- column_id: b99ae6a4-5597-43e6-94e4-aa63d3a8aa78
    `buy_down_fee_income_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_income_type',
    -- column_id: cff6f5ce-4564-4b83-8783-d9548a45593c
    `allow_full_term_for_tranche` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_full_term_for_tranche',
    -- column_id: d5ac472d-dc51-4ebe-80c9-9f57cc21c075
    `repayment_start_date_type_enum` SMALLINT NULL COMMENT 'Fineract source column repayment_start_date_type_enum',
    -- column_id: 981b87cf-ae55-4f69-8f55-5e115e81406b
    `enable_auto_repayment_for_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_auto_repayment_for_down_payment',
    -- column_id: de59c5ef-42c6-4269-a118-a1f3e839bec7
    `loan_schedule_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_type',
    -- column_id: 79391374-09e2-4e5d-ad50-373f128c1846
    `loan_schedule_processing_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_processing_type',
    -- column_id: 419df632-2bf8-4365-b6e6-76a338a7a5f5
    `fee_adjustments_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_adjustments_derived',
    -- column_id: 0d7f937c-e1b0-452c-9353-b80be3cba176
    `penalty_adjustments_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_adjustments_derived',
    -- column_id: ec18414e-b977-4624-94fa-0cced9aff758
    `fixed_length` SMALLINT NULL COMMENT 'Fineract source column fixed_length',
    -- column_id: b4ca72df-871b-4b88-8095-6f644ff4c5ff
    `supported_interest_refund_types` STRING NULL COMMENT 'Fineract source column supported_interest_refund_types',
    -- column_id: 5cf4db98-1035-4ed4-927a-305d74bfbd15
    `charge_off_behaviour` VARCHAR(20) NULL COMMENT 'Fineract source column charge_off_behaviour',
    -- column_id: 0287f5ac-b6fc-4302-b1a4-4def3c62070b
    `interest_recognition_on_disbursement_date` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recognition_on_disbursement_date',
    -- column_id: 7eaac2f6-190f-4939-b275-658401673b9b
    `installment_amount_in_multiples_of` DECIMAL(19,6) NULL COMMENT 'Fineract source column installment_amount_in_multiples_of',
    -- column_id: 5e20bcd8-f9d2-486b-8f01-31c8da8dff74
    `is_merchant_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column is_merchant_buy_down_fee',
    -- column_id: 2257e897-f865-405f-be58-d6a5961e179c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
