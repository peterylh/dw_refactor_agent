-- DWD account snapshot generated from m_savings_account
DROP TABLE IF EXISTS retail_banking_dm.dwd_deposit_account_daily_snapshot;
-- table_id: 2d4177d4-5f2d-4496-a019-63d525971c3e
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_deposit_account_daily_snapshot (
    -- column_id: 674edde8-1bc6-4c79-979d-95f514551c96
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a280ce5a-763d-4097-a5b7-6c002756d6b7
    `snapshot_date` DATE NOT NULL COMMENT 'Warehouse account snapshot date',
    -- column_id: 89a22d2e-189c-4a93-a4e1-b1414008c3a1
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 8749fd4b-a977-4bfc-8967-70ec3a7aa8d5
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 499f8c80-4a08-42ba-bb51-43eed36fd5f9
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 5c88af84-37be-41ab-91ff-0161901e9f72
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: ffc75514-212d-42ca-b40d-835ac7a760cf
    `gsim_id` BIGINT NULL COMMENT 'Fineract source column gsim_id',
    -- column_id: 250e19d5-b420-4753-9cae-46e716597d86
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 71112908-ff50-43d8-89c3-2872a3f59dca
    `field_officer_id` BIGINT NULL COMMENT 'Fineract source column field_officer_id',
    -- column_id: ebbb8058-6adf-499f-9fd8-8dd571908f07
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: ee46f917-cd6e-4da8-8ad9-4a5eb4d194f4
    `sub_status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column sub_status_enum',
    -- column_id: cc0c301f-23cb-468f-bcce-09618ec1e798
    `account_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column account_type_enum',
    -- column_id: ea3d035f-10e0-4584-9649-bde31e51d55b
    `deposit_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column deposit_type_enum',
    -- column_id: b0086c8b-782c-4efc-ac4d-70a911c1b298
    `submittedon_date` DATE NOT NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 93a03762-ac7c-4f77-b78a-1c916d36b19a
    `submittedon_userid` BIGINT NULL COMMENT 'Fineract source column submittedon_userid',
    -- column_id: 826380a7-f7b6-4417-b0a4-2fc5671a0d67
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: 1e7d2071-76a8-4d47-ab6a-274b4a519601
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: fa5d4391-aa1d-4b68-844a-f70225d2f226
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: a5f199ef-7faa-4241-974c-50d518f4e286
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: 82ed848a-d43f-4b0a-9781-2fb953dbdbb6
    `withdrawnon_date` DATE NULL COMMENT 'Fineract source column withdrawnon_date',
    -- column_id: 5ceccea9-b998-40dc-97cd-52afd3fcea28
    `withdrawnon_userid` BIGINT NULL COMMENT 'Fineract source column withdrawnon_userid',
    -- column_id: 975c35e2-ff64-4f57-a9e2-2287c5b07f55
    `activatedon_date` DATE NULL COMMENT 'Fineract source column activatedon_date',
    -- column_id: 67d4f340-dfc5-4cb3-aaad-f22480028d88
    `activatedon_userid` BIGINT NULL COMMENT 'Fineract source column activatedon_userid',
    -- column_id: 357ff004-73a5-4bb0-855a-eef9921f0394
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 20c89a86-b1cc-4d67-a099-9db7def33d0a
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 250cda2c-2df9-4c5c-856b-d80482372457
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 2797b8fa-3e07-4a49-89d9-cf9a8a81fe7d
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 9b15d450-2bc2-413b-bb51-b7c49ec145f2
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 879340fb-4565-4c73-ab54-cfb4145346b2
    `nominal_annual_interest_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column nominal_annual_interest_rate',
    -- column_id: 2b33b604-157f-4484-98ba-b1daf4bc0669
    `interest_compounding_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_compounding_period_enum',
    -- column_id: dbb7b066-e607-4269-a164-2ec6f3bf4fe2
    `interest_posting_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_posting_period_enum',
    -- column_id: ba877121-51a1-4f46-b3cf-7215a64b8066
    `interest_calculation_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_type_enum',
    -- column_id: dca662d2-06db-4bd3-aa6d-42d4d7a5de0e
    `interest_calculation_days_in_year_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_days_in_year_type_enum',
    -- column_id: d4ce563c-0c9b-4590-a3ef-7cc28e4818c4
    `min_required_opening_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_opening_balance',
    -- column_id: 00d056b9-746c-4915-aeef-a6c09b8d93de
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: 7eef5fb4-3874-460b-9410-715839030479
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: b069ea67-c52a-40e9-9198-1156483c9ba0
    `withdrawal_fee_for_transfer` BOOLEAN NULL COMMENT 'Fineract source column withdrawal_fee_for_transfer',
    -- column_id: 64753be0-f29b-423a-bbad-48c277b1f9ec
    `allow_overdraft` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_overdraft',
    -- column_id: 6beb65c1-ee2c-47a6-ae4c-f4d945b9e960
    `overdraft_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column overdraft_limit',
    -- column_id: 88830d56-6bdc-4be4-9b00-ea0ff02531ca
    `nominal_annual_interest_rate_overdraft` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_annual_interest_rate_overdraft',
    -- column_id: 0ad9865c-6de5-4b32-a33d-b9bdae963d7c
    `min_overdraft_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_overdraft_for_interest_calculation',
    -- column_id: 6fcab897-f9d2-43b7-844a-62a5693c51ec
    `lockedin_until_date_derived` DATE NULL COMMENT 'Fineract source column lockedin_until_date_derived',
    -- column_id: 19246848-e89d-41d3-b503-0d33036654ae
    `total_deposits_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_deposits_derived',
    -- column_id: 2b0cbe5e-7bdc-4acb-a555-92f68663ab6d
    `total_withdrawals_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_withdrawals_derived',
    -- column_id: 8628bc3a-3677-4905-a26c-4923cf1d150d
    `total_withdrawal_fees_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_withdrawal_fees_derived',
    -- column_id: b34bd8f9-3958-4c9a-b26f-45730a3448c3
    `total_fees_charge_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_fees_charge_derived',
    -- column_id: 139e5a50-6fa8-4ffe-9ca7-36fb49778348
    `total_penalty_charge_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_penalty_charge_derived',
    -- column_id: c0a4e09c-8463-4199-85a5-ea8ac560442e
    `total_annual_fees_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_annual_fees_derived',
    -- column_id: 0f4d913f-c732-49dc-a4eb-6f3a0824dcd9
    `total_interest_earned_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_interest_earned_derived',
    -- column_id: fd24f634-05a1-4593-bda5-1813f7651f35
    `total_interest_posted_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_interest_posted_derived',
    -- column_id: 11f371c9-200b-4aa9-9d04-a436a8c345b3
    `total_overdraft_interest_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_overdraft_interest_derived',
    -- column_id: 7d3689df-8a1f-4408-b8c3-67447a8fd13d
    `total_withhold_tax_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_withhold_tax_derived',
    -- column_id: e509386b-d8f4-4611-9ba2-9451b519c3ec
    `account_balance_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column account_balance_derived',
    -- column_id: d0e08285-cc03-4d4f-a7d5-8f4e037d2db8
    `min_required_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_balance',
    -- column_id: 58faf9d9-685d-46a8-b333-da310c947b4c
    `enforce_min_required_balance` BOOLEAN NOT NULL COMMENT 'Fineract source column enforce_min_required_balance',
    -- column_id: c4ea3b38-0cb2-4fa3-a0f1-b19c58671946
    `min_balance_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_balance_for_interest_calculation',
    -- column_id: b29250f1-61cf-48e8-9b92-080572de7fbd
    `start_interest_calculation_date` DATE NULL COMMENT 'Fineract source column start_interest_calculation_date',
    -- column_id: 47f25544-2ee2-49dd-98fa-5413baafb824
    `on_hold_funds_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column on_hold_funds_derived',
    -- column_id: 8e7bee08-f2a9-4259-9812-91bcfc9538d0
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 566ff66e-ef05-4f28-8257-a88299f87057
    `withhold_tax` BOOLEAN NOT NULL COMMENT 'Fineract source column withhold_tax',
    -- column_id: 38791eb1-1686-4bd0-8021-ed13028ed7bc
    `tax_group_id` BIGINT NULL COMMENT 'Fineract source column tax_group_id',
    -- column_id: a80051db-9865-4f5c-8290-d9f5ed76fa61
    `last_interest_calculation_date` DATE NULL COMMENT 'Fineract source column last_interest_calculation_date',
    -- column_id: 121839fd-eb3b-403b-9f0c-a49328171a60
    `total_savings_amount_on_hold` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_savings_amount_on_hold',
    -- column_id: a8e7c327-a156-413e-9cfe-cdbb9ffc5645
    `interest_posted_till_date` DATE NULL COMMENT 'Fineract source column interest_posted_till_date',
    -- column_id: d238421a-f4be-488c-9be1-f71c1e38f647
    `reason_for_block` VARCHAR(256) NULL COMMENT 'Fineract source column reason_for_block',
    -- column_id: 5ef84d7e-251e-4301-b536-bdafe1d964e5
    `max_allowed_lien_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_allowed_lien_limit',
    -- column_id: 69a6ee11-86df-4103-be00-b699c9039679
    `is_lien_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_lien_allowed',
    -- column_id: e7024f5b-54a5-48f5-8188-ec394b22684d
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 56ba0ea0-fdd4-4f85-b213-2975c737f34a
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 6702dd76-4ef3-489b-a8c1-f629791da0b9
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 6d462a1d-3884-4045-b55a-d0c96577d24c
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 700ce69d-2c3f-4586-883f-5645f186e429
    `accrued_till_date` DATE NULL COMMENT 'Fineract source column accrued_till_date',
    -- column_id: 017bdfef-26fe-48ba-8f63-1ac3f6a8e40d
    `last_closed_business_date` DATE NULL COMMENT 'Fineract source column last_closed_business_date',
    -- column_id: 4593d397-ecf7-41de-bcef-40a6015efa0f
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `snapshot_date`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
