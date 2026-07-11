-- ODS mirror of Apache Fineract m_product_loan (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan;
-- table_id: 693654a6-a7fa-47c0-bea2-9a7916d58200
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan (
    -- column_id: 2d95fc5d-6e5a-4d60-bf14-1076d43288e7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1b2ec8e9-f177-426c-83c2-09bc012aa762
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: 9e6cb020-ab07-485a-a8e4-b5b0f9c3d06e
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: d82a2ba8-4251-41e6-9766-6a7c1c472855
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 1fbda5d7-63e1-45f9-8de8-a5fc52beb2cf
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 64d40735-404b-4413-a72a-4203ce5dac3f
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: bc8e258e-bc02-49fb-bea0-92820f57cf89
    `min_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_principal_amount',
    -- column_id: ba7e251d-c60d-49b8-9044-36163cef2f7e
    `max_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_principal_amount',
    -- column_id: 193eab3f-300f-4276-ba43-559bd38415cb
    `arrearstolerance_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column arrearstolerance_amount',
    -- column_id: 3595dfc3-618a-4d1f-a9f1-5d0b7812f48e
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 13616b59-20af-4a30-b6f5-6b5ed3fcff32
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: c0e2c295-1700-41a0-a114-8ba624189c8b
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: b0eeddc7-0c76-4033-b988-9611720069a4
    `is_linked_to_floating_interest_rates` BOOLEAN NOT NULL COMMENT 'Fineract source column is_linked_to_floating_interest_rates',
    -- column_id: 571e449c-2d4c-4818-8f16-dd2f76f7f2f0
    `allow_variabe_installments` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_variabe_installments',
    -- column_id: cd024dba-3af4-4e36-8024-16d6a39fc704
    `nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_interest_rate_per_period',
    -- column_id: 3a120cb1-d480-4f33-948a-51d72b5877e6
    `min_nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_nominal_interest_rate_per_period',
    -- column_id: f85568b3-d7ef-4c50-87aa-91ef1592b1ab
    `max_nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_nominal_interest_rate_per_period',
    -- column_id: e4699479-1875-4b2c-a9e1-1faa53195c9a
    `interest_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column interest_period_frequency_enum',
    -- column_id: 5d004cd8-88bd-4d03-8145-6557368b457c
    `annual_nominal_interest_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column annual_nominal_interest_rate',
    -- column_id: 72c950cb-cef0-4674-8a48-1e95ce9f732d
    `interest_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_method_enum',
    -- column_id: 1a587e70-b4bd-4216-84d2-91c162ae34f0
    `interest_calculated_in_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculated_in_period_enum',
    -- column_id: 30aac936-c9ab-4c5f-8292-7f338bc9779a
    `allow_partial_period_interest_calcualtion` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_partial_period_interest_calcualtion',
    -- column_id: 3cd8be64-d3ef-4ec3-9fae-c52ce5071cc6
    `repay_every` SMALLINT NOT NULL COMMENT 'Fineract source column repay_every',
    -- column_id: d6d5e243-f0c5-42a5-a237-f40228a268f9
    `repayment_period_frequency_enum` SMALLINT NOT NULL COMMENT 'Fineract source column repayment_period_frequency_enum',
    -- column_id: c61e3557-2a34-453a-b16e-9b697b440c12
    `number_of_repayments` SMALLINT NOT NULL COMMENT 'Fineract source column number_of_repayments',
    -- column_id: cfee01f8-51e9-4de9-ac4b-00a263900c1d
    `min_number_of_repayments` SMALLINT NULL COMMENT 'Fineract source column min_number_of_repayments',
    -- column_id: a87f4c2a-de2c-4edb-95a5-f7b1cb463671
    `max_number_of_repayments` SMALLINT NULL COMMENT 'Fineract source column max_number_of_repayments',
    -- column_id: 71b03d25-7079-46d0-b904-ecbb1488cd7d
    `grace_on_principal_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_principal_periods',
    -- column_id: af2a4fd9-018d-4815-97e8-64dc91c5ce5d
    `recurring_moratorium_principal_periods` SMALLINT NULL COMMENT 'Fineract source column recurring_moratorium_principal_periods',
    -- column_id: f23b002a-6e17-4643-b98f-0c0e17a040e2
    `grace_on_interest_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_interest_periods',
    -- column_id: 4c625bac-b748-455d-94de-84496c6f7b32
    `grace_interest_free_periods` SMALLINT NULL COMMENT 'Fineract source column grace_interest_free_periods',
    -- column_id: 623fd172-5606-493a-851f-17d799934339
    `amortization_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column amortization_method_enum',
    -- column_id: b9de1dd9-ab7e-45a0-b61e-d15b4ad50221
    `accounting_type` SMALLINT NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: 99152f24-79a3-4ca1-8a31-e0965981b493
    `loan_transaction_strategy_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_strategy_id',
    -- column_id: e4d250a6-d0a7-4bf7-807a-178592c77c4c
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 90ab32d3-e624-4ed5-9e92-a20832b0fc1c
    `include_in_borrower_cycle` BOOLEAN NOT NULL COMMENT 'Fineract source column include_in_borrower_cycle',
    -- column_id: d903d15a-46f9-4686-9a10-c6b8fb9c9b9f
    `use_borrower_cycle` BOOLEAN NOT NULL COMMENT 'Fineract source column use_borrower_cycle',
    -- column_id: 008a4e60-e755-43af-a559-3a8cac6a3fd3
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: ed854b7b-3ee5-402b-900a-180160d57884
    `close_date` DATE NULL COMMENT 'Fineract source column close_date',
    -- column_id: b0ed2ee3-3a59-498e-8892-eb9c82568588
    `allow_multiple_disbursals` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_multiple_disbursals',
    -- column_id: 90d3584d-1b9c-4056-921c-a4593e88cc19
    `max_disbursals` INT NULL COMMENT 'Fineract source column max_disbursals',
    -- column_id: cd73f4b6-cadc-4771-8b63-599a0cbc926a
    `max_outstanding_loan_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_outstanding_loan_balance',
    -- column_id: fad78706-ee6d-4208-b5b6-55257546eda3
    `grace_on_arrears_ageing` SMALLINT NULL COMMENT 'Fineract source column grace_on_arrears_ageing',
    -- column_id: 968baf9f-1abd-454c-b443-26f990f8ab4a
    `overdue_days_for_npa` SMALLINT NULL COMMENT 'Fineract source column overdue_days_for_npa',
    -- column_id: f44e4b93-aca9-4084-871d-77b5a1ce92c1
    `days_in_month_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_month_enum',
    -- column_id: 13937b05-c711-46b4-87d6-ec8290e0c9e6
    `days_in_year_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_year_enum',
    -- column_id: 479d0e8d-83f3-4570-b95d-07a193aace6c
    `interest_recalculation_enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recalculation_enabled',
    -- column_id: 3c4f8a10-e3d2-4ef2-8a34-aee205340c57
    `min_days_between_disbursal_and_first_repayment` INT NULL COMMENT 'Fineract source column min_days_between_disbursal_and_first_repayment',
    -- column_id: d2d5c480-5f1d-48ad-98d7-4b454c47fe43
    `hold_guarantee_funds` BOOLEAN NOT NULL COMMENT 'Fineract source column hold_guarantee_funds',
    -- column_id: f4c59dfa-2bba-4b53-bb71-4650ca72dc8c
    `principal_threshold_for_last_installment` DECIMAL(5,2) NOT NULL COMMENT 'Fineract source column principal_threshold_for_last_installment',
    -- column_id: 14160df9-2302-4889-8737-4e366c2c46c6
    `account_moves_out_of_npa_only_on_arrears_completion` BOOLEAN NOT NULL COMMENT 'Fineract source column account_moves_out_of_npa_only_on_arrears_completion',
    -- column_id: 4fa4c078-9804-4bf3-a78a-c988aad434c9
    `can_define_fixed_emi_amount` BOOLEAN NOT NULL COMMENT 'Fineract source column can_define_fixed_emi_amount',
    -- column_id: 80145fe9-0683-4e88-b105-cb3c71cd22d4
    `installment_amount_in_multiples_of` DECIMAL(19,6) NULL COMMENT 'Fineract source column installment_amount_in_multiples_of',
    -- column_id: 4967c2a4-034b-4c0d-81b6-1b916c357f4f
    `can_use_for_topup` BOOLEAN NOT NULL COMMENT 'Fineract source column can_use_for_topup',
    -- column_id: 4ec08669-be56-4f8c-92e4-40b47c744640
    `sync_expected_with_disbursement_date` BOOLEAN NULL COMMENT 'Fineract source column sync_expected_with_disbursement_date',
    -- column_id: 6ef8c66b-630f-4077-af43-9657585b210f
    `is_equal_amortization` BOOLEAN NOT NULL COMMENT 'Fineract source column is_equal_amortization',
    -- column_id: bca8f621-cc8b-4b42-a904-46224ed048fb
    `fixed_principal_percentage_per_installment` DECIMAL(5,2) NULL COMMENT 'Fineract source column fixed_principal_percentage_per_installment',
    -- column_id: a91a61e6-0bc4-4639-a491-27368e8d73ae
    `disallow_expected_disbursements` BOOLEAN NOT NULL COMMENT 'Fineract source column disallow_expected_disbursements',
    -- column_id: 639a0e4f-2d8f-43e9-b598-68fcacbf6474
    `allow_approved_disbursed_amounts_over_applied` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_approved_disbursed_amounts_over_applied',
    -- column_id: 7932dad4-c730-4b0f-99fb-f34f99dd9775
    `over_applied_calculation_type` VARCHAR(10) NULL COMMENT 'Fineract source column over_applied_calculation_type',
    -- column_id: 375f435e-6dd7-4e28-9cf6-7e2009f48a66
    `over_applied_number` INT NULL COMMENT 'Fineract source column over_applied_number',
    -- column_id: 8f1f0c45-a017-4310-826d-0111384c3701
    `delinquency_bucket_id` BIGINT NULL COMMENT 'Fineract source column delinquency_bucket_id',
    -- column_id: 73409583-a11c-497d-a134-7595937c6f30
    `loan_transaction_strategy_code` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_code',
    -- column_id: 75984578-f890-47b2-8a9a-ee08b7538996
    `loan_transaction_strategy_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_name',
    -- column_id: 7141a6e8-230f-4bc9-a574-77bc837bbbe4
    `due_days_for_repayment_event` INT NULL COMMENT 'Fineract source column due_days_for_repayment_event',
    -- column_id: 586e7aea-a26f-40cc-8cef-ff5af150f438
    `overdue_days_for_repayment_event` INT NULL COMMENT 'Fineract source column overdue_days_for_repayment_event',
    -- column_id: 4158d18f-25e2-4d01-881e-57480f47a5d2
    `enable_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_down_payment',
    -- column_id: e575eb30-ed84-4aaa-b20a-bc40cdbd309c
    `disbursed_amount_percentage_for_down_payment` DECIMAL(9,6) NULL COMMENT 'Fineract source column disbursed_amount_percentage_for_down_payment',
    -- column_id: c936c6ee-89ed-4f18-9191-8c74d2638445
    `enable_installment_level_delinquency` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_installment_level_delinquency',
    -- column_id: 2268c5fb-b89e-4e84-8714-14eadbecaa23
    `enable_accrual_activity_posting` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_accrual_activity_posting',
    -- column_id: a81787d5-b5fc-437b-81c6-3c590608633a
    `days_in_year_custom_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column days_in_year_custom_strategy',
    -- column_id: a4b1826a-919f-4c87-9c54-e9502e4882ac
    `enable_income_capitalization` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_income_capitalization',
    -- column_id: d62eea94-144c-409b-be70-aa9ada968101
    `capitalized_income_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_calculation_type',
    -- column_id: f6c988f4-c5eb-4f7f-be28-cbb3944230eb
    `capitalized_income_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_strategy',
    -- column_id: 641a3dc2-00b8-41f8-8f4c-646b57c3ebcb
    `capitalized_income_type` VARCHAR(10) NULL COMMENT 'Fineract source column capitalized_income_type',
    -- column_id: 38e0a066-e4a7-479a-b74d-d05cc2ff2452
    `enable_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_buy_down_fee',
    -- column_id: 0bea9f6c-de11-4c22-917a-39fb15a5584e
    `buy_down_fee_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_calculation_type',
    -- column_id: 3124e709-26ea-4d72-84ce-6fcc2f9480f0
    `buy_down_fee_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_strategy',
    -- column_id: 77bc39ad-fbe9-418b-9a7a-0fa6972ae240
    `buy_down_fee_income_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_income_type',
    -- column_id: 87873f6e-3557-4be2-9881-71c75232e9a2
    `allow_full_term_for_tranche` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_full_term_for_tranche',
    -- column_id: 5b676b6d-141a-4122-b53c-dd59994fc5aa
    `enable_auto_repayment_for_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_auto_repayment_for_down_payment',
    -- column_id: 90d7318f-ce93-4b3b-808d-fac50b6d05c1
    `repayment_start_date_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column repayment_start_date_type_enum',
    -- column_id: 0ae642d2-1bd9-4274-89ac-45d34ac8f0eb
    `loan_schedule_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_type',
    -- column_id: 4b545476-2fa5-43e5-be63-b0ed2370b54d
    `loan_schedule_processing_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_processing_type',
    -- column_id: b1830741-69df-4ea9-a684-ee6d2119f518
    `fixed_length` SMALLINT NULL COMMENT 'Fineract source column fixed_length',
    -- column_id: e72cde12-18a2-42b2-a672-75fa675d8812
    `supported_interest_refund_types` STRING NULL COMMENT 'Fineract source column supported_interest_refund_types',
    -- column_id: 5c104684-6036-440c-adfb-65a956be7d4b
    `charge_off_behaviour` VARCHAR(20) NULL COMMENT 'Fineract source column charge_off_behaviour',
    -- column_id: 73904bf6-5562-4301-941e-893580c80c53
    `interest_recognition_on_disbursement_date` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recognition_on_disbursement_date',
    -- column_id: 2abcb702-6727-4ed7-9af8-b18871dc7734
    `is_merchant_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column is_merchant_buy_down_fee',
    -- column_id: a5a03092-b42d-4205-b5af-a9a4649fab0e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
