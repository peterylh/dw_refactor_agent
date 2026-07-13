-- DIM generated from m_product_loan
DROP TABLE IF EXISTS retail_banking_dm.dim_loan_product;
-- table_id: 266bd19a-1ad6-44c2-98f0-bfde9258c898
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_loan_product (
    -- column_id: e0096e29-4f9f-4d71-97f6-427139480a1d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 8197aec1-c39b-4a90-9bf2-67ea9acd200d
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: 449d9473-0b07-463c-b76c-8ef8e78ee86e
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 5b071a19-c9cd-460a-869f-082f6aa9a8e6
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 0da98486-ab09-4f21-911b-93e5cefe2d4b
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 42efe414-7df3-446f-9895-4e2a3d6d7908
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: 3246b7e7-d355-4144-9bc5-3480c018fc02
    `min_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_principal_amount',
    -- column_id: 9a19625b-5eff-47ce-a3f1-93dbe3eb09c9
    `max_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_principal_amount',
    -- column_id: 9c86f9c4-c430-451a-954d-48f00a130898
    `arrearstolerance_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column arrearstolerance_amount',
    -- column_id: dec3b2fa-31f3-42bf-a069-0b1201a0036f
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 910abb72-aa78-4947-9616-21164de07f25
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: dd6fe112-cfeb-4e29-84c5-cfc4af406ee8
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: 4e0495c0-9464-4d13-b004-4aababdcab23
    `is_linked_to_floating_interest_rates` BOOLEAN NOT NULL COMMENT 'Fineract source column is_linked_to_floating_interest_rates',
    -- column_id: 3bbd9268-fe8d-4c5d-86b2-66f95a8e65f0
    `allow_variabe_installments` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_variabe_installments',
    -- column_id: 54aaee84-0ce2-4f4f-8605-c6286fa06ed9
    `nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_interest_rate_per_period',
    -- column_id: 8f8eb2ff-6ca2-4906-b8f3-a884fed837e2
    `min_nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_nominal_interest_rate_per_period',
    -- column_id: 87490578-56dd-4451-a4e2-7b5e7ce80dfc
    `max_nominal_interest_rate_per_period` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_nominal_interest_rate_per_period',
    -- column_id: ae957e91-1f5e-4871-9b8f-0b9173396f59
    `interest_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column interest_period_frequency_enum',
    -- column_id: 4d9e79a9-ff7b-428f-896e-085978006a6a
    `annual_nominal_interest_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column annual_nominal_interest_rate',
    -- column_id: 2d7ca311-0442-4047-af27-b20a27595607
    `interest_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_method_enum',
    -- column_id: 618ad2f0-8e75-4d94-829b-9a98d77478b6
    `interest_calculated_in_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculated_in_period_enum',
    -- column_id: d45bf47a-ca09-4a36-880b-b08895b4aa5d
    `allow_partial_period_interest_calcualtion` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_partial_period_interest_calcualtion',
    -- column_id: 21bd7b6a-70da-4651-be2f-18e257e81402
    `repay_every` SMALLINT NOT NULL COMMENT 'Fineract source column repay_every',
    -- column_id: 3ee49013-84b0-40f6-a844-9bbd95e361aa
    `repayment_period_frequency_enum` SMALLINT NOT NULL COMMENT 'Fineract source column repayment_period_frequency_enum',
    -- column_id: 6fd553a1-9b60-43c2-8ec2-f4295876d08f
    `number_of_repayments` SMALLINT NOT NULL COMMENT 'Fineract source column number_of_repayments',
    -- column_id: 5303883a-b8bb-464e-a4f8-d941854acc7e
    `min_number_of_repayments` SMALLINT NULL COMMENT 'Fineract source column min_number_of_repayments',
    -- column_id: 98392d2f-2966-4393-9a4f-8f2a2a3fcd46
    `max_number_of_repayments` SMALLINT NULL COMMENT 'Fineract source column max_number_of_repayments',
    -- column_id: abf396d7-206e-437b-857e-33789bf12d08
    `grace_on_principal_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_principal_periods',
    -- column_id: 45a36ffd-b6f1-462c-9153-331136ad5b5f
    `recurring_moratorium_principal_periods` SMALLINT NULL COMMENT 'Fineract source column recurring_moratorium_principal_periods',
    -- column_id: d81becf7-d464-428b-8bea-777b6ba91060
    `grace_on_interest_periods` SMALLINT NULL COMMENT 'Fineract source column grace_on_interest_periods',
    -- column_id: 61cee067-c89e-4cfb-9a6c-6768d87c6d1a
    `grace_interest_free_periods` SMALLINT NULL COMMENT 'Fineract source column grace_interest_free_periods',
    -- column_id: 4a7d2b56-89f3-4b04-807c-04c50aead64c
    `amortization_method_enum` SMALLINT NOT NULL COMMENT 'Fineract source column amortization_method_enum',
    -- column_id: d105c81e-7e84-491a-87a4-38e8dc6b4620
    `accounting_type` SMALLINT NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: ef69a80e-f364-4193-9cb6-4fafe46d1ff6
    `loan_transaction_strategy_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_strategy_id',
    -- column_id: 7d3c2e77-756a-47ba-af86-565e9dd8475a
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: a23134f2-8d64-4416-9344-212fae5d3e0f
    `include_in_borrower_cycle` BOOLEAN NOT NULL COMMENT 'Fineract source column include_in_borrower_cycle',
    -- column_id: 98329d8d-5ebd-48e9-968e-bc82c80b7151
    `use_borrower_cycle` BOOLEAN NOT NULL COMMENT 'Fineract source column use_borrower_cycle',
    -- column_id: 93cdebbf-e2fd-4ced-a0a9-9f3bc58f0ffc
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: cc41c1ff-8c91-49a8-8225-b5cc498e69d9
    `close_date` DATE NULL COMMENT 'Fineract source column close_date',
    -- column_id: 0788a1a3-4381-4917-aada-40dedffaace4
    `allow_multiple_disbursals` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_multiple_disbursals',
    -- column_id: cdb0d80a-24ef-41fc-8d3d-0984574d6e26
    `max_disbursals` INT NULL COMMENT 'Fineract source column max_disbursals',
    -- column_id: 2d837d34-6d36-4557-a9f5-695afc7a92ec
    `max_outstanding_loan_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_outstanding_loan_balance',
    -- column_id: d5f11738-9644-4d67-a4f1-69b2af70a0d9
    `grace_on_arrears_ageing` SMALLINT NULL COMMENT 'Fineract source column grace_on_arrears_ageing',
    -- column_id: 257acea2-d046-4df2-b476-9ddd5f373744
    `overdue_days_for_npa` SMALLINT NULL COMMENT 'Fineract source column overdue_days_for_npa',
    -- column_id: 9ad9d104-697f-4049-8c59-010a2446eaca
    `days_in_month_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_month_enum',
    -- column_id: 11eb723b-cd95-437d-89f0-8e1ab6ca9625
    `days_in_year_enum` SMALLINT NOT NULL COMMENT 'Fineract source column days_in_year_enum',
    -- column_id: 8b2814d5-28ec-4794-bbdf-ff7e23ed8855
    `interest_recalculation_enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recalculation_enabled',
    -- column_id: a7ea54f3-5078-4c39-882d-50f8853a628f
    `min_days_between_disbursal_and_first_repayment` INT NULL COMMENT 'Fineract source column min_days_between_disbursal_and_first_repayment',
    -- column_id: d3badb1c-da57-493b-a311-caf84b0dfd4c
    `hold_guarantee_funds` BOOLEAN NOT NULL COMMENT 'Fineract source column hold_guarantee_funds',
    -- column_id: 7062c610-3a07-41bb-8967-a1b14847f88d
    `principal_threshold_for_last_installment` DECIMAL(5,2) NOT NULL COMMENT 'Fineract source column principal_threshold_for_last_installment',
    -- column_id: a2141271-8f7f-4af6-88b0-b9f3541d10ee
    `account_moves_out_of_npa_only_on_arrears_completion` BOOLEAN NOT NULL COMMENT 'Fineract source column account_moves_out_of_npa_only_on_arrears_completion',
    -- column_id: b005cc6e-40ff-4bc4-bcb4-b0eafdb3883b
    `can_define_fixed_emi_amount` BOOLEAN NOT NULL COMMENT 'Fineract source column can_define_fixed_emi_amount',
    -- column_id: df902cb4-1ac7-4ec3-8acb-a999eb631845
    `installment_amount_in_multiples_of` DECIMAL(19,6) NULL COMMENT 'Fineract source column installment_amount_in_multiples_of',
    -- column_id: e20c7c37-8e2b-44a3-a682-fc7397912c9d
    `can_use_for_topup` BOOLEAN NOT NULL COMMENT 'Fineract source column can_use_for_topup',
    -- column_id: fe9cca06-6e93-4a40-ae79-c546bafc10ee
    `sync_expected_with_disbursement_date` BOOLEAN NULL COMMENT 'Fineract source column sync_expected_with_disbursement_date',
    -- column_id: 403f6c4b-5dc0-4531-b7ee-54ad0e5e2f7a
    `is_equal_amortization` BOOLEAN NOT NULL COMMENT 'Fineract source column is_equal_amortization',
    -- column_id: 2d477521-33e8-4791-9d0e-dbff052a33b3
    `fixed_principal_percentage_per_installment` DECIMAL(5,2) NULL COMMENT 'Fineract source column fixed_principal_percentage_per_installment',
    -- column_id: a74d03de-2fee-42d2-a8f3-689f643d46ba
    `disallow_expected_disbursements` BOOLEAN NOT NULL COMMENT 'Fineract source column disallow_expected_disbursements',
    -- column_id: 7008df3e-8b0e-4b84-9550-c2d156be95b1
    `allow_approved_disbursed_amounts_over_applied` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_approved_disbursed_amounts_over_applied',
    -- column_id: 60148175-6770-4e20-ac8d-4d88db0f955d
    `over_applied_calculation_type` VARCHAR(10) NULL COMMENT 'Fineract source column over_applied_calculation_type',
    -- column_id: 40387867-252e-436c-b794-a530a84c4d9f
    `over_applied_number` INT NULL COMMENT 'Fineract source column over_applied_number',
    -- column_id: 762993b1-47f9-461d-89fd-735638aff596
    `delinquency_bucket_id` BIGINT NULL COMMENT 'Fineract source column delinquency_bucket_id',
    -- column_id: b904bee9-753a-4eea-b00f-4859be199e34
    `loan_transaction_strategy_code` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_code',
    -- column_id: 630d41f3-ae49-40fc-9627-a5575c37d34f
    `loan_transaction_strategy_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_name',
    -- column_id: 6f086f7c-7b5b-4511-80bb-fdd27188ba2b
    `due_days_for_repayment_event` INT NULL COMMENT 'Fineract source column due_days_for_repayment_event',
    -- column_id: 07a0dc2a-3dd0-49f3-acb1-561983a30333
    `overdue_days_for_repayment_event` INT NULL COMMENT 'Fineract source column overdue_days_for_repayment_event',
    -- column_id: bdf114ec-b817-4185-a4f7-5b8d96c1af45
    `enable_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_down_payment',
    -- column_id: a80bc683-7fa4-4707-896c-5b8be8def639
    `disbursed_amount_percentage_for_down_payment` DECIMAL(9,6) NULL COMMENT 'Fineract source column disbursed_amount_percentage_for_down_payment',
    -- column_id: 1e13a26c-d5de-452d-9eb2-f5924e125bcc
    `enable_installment_level_delinquency` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_installment_level_delinquency',
    -- column_id: 13e8e9ab-b10a-43ce-94c2-a24e46d62e13
    `enable_accrual_activity_posting` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_accrual_activity_posting',
    -- column_id: 246e1f42-4e23-45ee-8a2b-9e84cc63be7c
    `days_in_year_custom_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column days_in_year_custom_strategy',
    -- column_id: 073c3f64-9e58-4859-b4ff-dcd8a98faf16
    `enable_income_capitalization` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_income_capitalization',
    -- column_id: a98518b0-bf2f-4b3c-96c4-2ae401c36e26
    `capitalized_income_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_calculation_type',
    -- column_id: f977662f-5e0c-4b46-a039-426d4056d64d
    `capitalized_income_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column capitalized_income_strategy',
    -- column_id: f65a0a84-6dc2-4061-a32f-5bcebe36ed77
    `capitalized_income_type` VARCHAR(10) NULL COMMENT 'Fineract source column capitalized_income_type',
    -- column_id: 584f8676-0f1b-48a4-84b0-73bad854dd27
    `enable_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_buy_down_fee',
    -- column_id: 96d0a6a1-fcb9-458b-b698-bbc13000858e
    `buy_down_fee_calculation_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_calculation_type',
    -- column_id: 9ccd559a-a76f-416c-b768-77762e854cb0
    `buy_down_fee_strategy` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_strategy',
    -- column_id: f8122779-a950-4dcb-9292-0481a696d21a
    `buy_down_fee_income_type` VARCHAR(100) NULL COMMENT 'Fineract source column buy_down_fee_income_type',
    -- column_id: 27484dcd-cedb-40e0-9f7a-7b2153a8782a
    `allow_full_term_for_tranche` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_full_term_for_tranche',
    -- column_id: 26647800-81ed-4c56-86e9-c54afb2163d4
    `enable_auto_repayment_for_down_payment` BOOLEAN NOT NULL COMMENT 'Fineract source column enable_auto_repayment_for_down_payment',
    -- column_id: c94282ca-50d6-42d1-ac19-a8173c1a6d68
    `repayment_start_date_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column repayment_start_date_type_enum',
    -- column_id: 94032a93-c0ec-49a5-af25-52121246d629
    `loan_schedule_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_type',
    -- column_id: 1013900a-0c01-4da9-a186-763fb59c1b4b
    `loan_schedule_processing_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column loan_schedule_processing_type',
    -- column_id: 57482fb5-20c8-457b-bb20-23ae2981e29b
    `fixed_length` SMALLINT NULL COMMENT 'Fineract source column fixed_length',
    -- column_id: b8edd431-df01-458b-9c8e-4c48c91f27fe
    `supported_interest_refund_types` STRING NULL COMMENT 'Fineract source column supported_interest_refund_types',
    -- column_id: 7e5906a0-e3ee-4b07-bfd7-02b975878c2b
    `charge_off_behaviour` VARCHAR(20) NULL COMMENT 'Fineract source column charge_off_behaviour',
    -- column_id: a003af0e-4620-4fbe-b010-110288c42827
    `interest_recognition_on_disbursement_date` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_recognition_on_disbursement_date',
    -- column_id: 4aad45ff-7f69-4df8-b9c0-c225da91b999
    `is_merchant_buy_down_fee` BOOLEAN NOT NULL COMMENT 'Fineract source column is_merchant_buy_down_fee',
    -- column_id: f50d1fbd-79b2-4f71-a681-e4370e4e0b70
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
