-- ODS mirror of Apache Fineract m_savings_account (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_account;
-- table_id: 7659e01e-a4d7-45da-8ef1-0a95290eb68e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_account (
    -- column_id: b74f34b6-37aa-469d-8092-7958a95a9c9f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f4092c79-5092-4821-ac90-c707b4174c0c
    `account_no` VARCHAR(20) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 2e7245c0-fd2b-44cc-9b3f-32efd07cfa1e
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 37e9d5b7-3af5-4f92-af2d-9218bf9ecd2f
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 0b424df4-9bd9-43c5-8b8b-8f051c6825c2
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 3e2ed43d-70a4-4ee6-9319-9523ce2e5757
    `gsim_id` BIGINT NULL COMMENT 'Fineract source column gsim_id',
    -- column_id: 058285e0-03fc-4dc5-8433-3fdbf0e20885
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: c591daf5-2710-4102-8ee4-ee16ddd002a3
    `field_officer_id` BIGINT NULL COMMENT 'Fineract source column field_officer_id',
    -- column_id: 65f19660-7a09-4fec-ae73-7df45568958d
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: fce2794a-7394-449a-9de7-c351fa59bba4
    `sub_status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column sub_status_enum',
    -- column_id: 180d6524-7d6a-4bb8-ae31-c01d3cbb5b3f
    `account_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column account_type_enum',
    -- column_id: d37f367a-9a1d-479b-a55f-514e2e718dd1
    `deposit_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column deposit_type_enum',
    -- column_id: feb1e076-ef52-4ef6-a312-7cacbd9ad6ed
    `submittedon_date` DATE NOT NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 33253ff4-5b3b-4f1a-b27e-3fce276f1cdb
    `submittedon_userid` BIGINT NULL COMMENT 'Fineract source column submittedon_userid',
    -- column_id: 6a986ad9-d397-4db3-ab7f-df38c3cb36db
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: 3bb471c7-a8b4-45b9-8371-b1968726aa99
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: 13cc99c3-a016-48d3-80d8-99001ad6d0e7
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: 2a731689-bc37-4e0e-9d7d-25858a89c97e
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: c709e364-63c5-4e6d-bb1f-80efd0348080
    `withdrawnon_date` DATE NULL COMMENT 'Fineract source column withdrawnon_date',
    -- column_id: a21d76f1-c359-4eb0-a919-64bea02ccdd9
    `withdrawnon_userid` BIGINT NULL COMMENT 'Fineract source column withdrawnon_userid',
    -- column_id: e199ad73-4b05-4639-8d90-5de0d90c026b
    `activatedon_date` DATE NULL COMMENT 'Fineract source column activatedon_date',
    -- column_id: d2d8b904-3835-49e5-bc17-763fc464f4be
    `activatedon_userid` BIGINT NULL COMMENT 'Fineract source column activatedon_userid',
    -- column_id: 2d159f30-bde4-420c-ba3d-0e69ea404317
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 66c1969f-22b7-4186-a30d-676ecaa8a036
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 26aae820-e1e8-4074-9022-2ed2e0afcf45
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 5785d0e9-759a-4ae4-93df-fe57c8995a8b
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: c8317cf4-1998-458a-8a8d-0a5abea0d6ae
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 301ed700-6baf-4da3-a86d-7a9b0d17ed91
    `nominal_annual_interest_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column nominal_annual_interest_rate',
    -- column_id: 9b354adc-991f-4a1a-a412-b33317367fa1
    `interest_compounding_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_compounding_period_enum',
    -- column_id: dae99f53-d18c-48f6-9c39-7a7ce0bd8f31
    `interest_posting_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_posting_period_enum',
    -- column_id: da1a4496-f6ec-429b-ae8a-eff2f6c496b8
    `interest_calculation_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_type_enum',
    -- column_id: cc444222-e337-4019-b167-588606002d04
    `interest_calculation_days_in_year_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_days_in_year_type_enum',
    -- column_id: dcd0d7e6-e205-45f7-bb1a-b59fb51c1c07
    `min_required_opening_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_opening_balance',
    -- column_id: d64bdb82-4ac7-4012-ac2b-5e8c3cf3e411
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: c7af9a7b-c94e-425f-b0af-69958aeb2ad4
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: 5571a2bb-3edb-4e21-b9af-0bddfe233423
    `withdrawal_fee_for_transfer` BOOLEAN NULL COMMENT 'Fineract source column withdrawal_fee_for_transfer',
    -- column_id: 847ec028-b83b-433a-95fb-8dec8f669fed
    `allow_overdraft` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_overdraft',
    -- column_id: c97bff0c-78c2-4937-8841-e2af4179e494
    `overdraft_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column overdraft_limit',
    -- column_id: fea05b3e-dfc6-4187-a2a0-01b6f18caa6f
    `nominal_annual_interest_rate_overdraft` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_annual_interest_rate_overdraft',
    -- column_id: 0bd869c8-2cf7-48a7-a815-cc00bef5fa0c
    `min_overdraft_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_overdraft_for_interest_calculation',
    -- column_id: 5a7d5575-25b0-413e-9f6e-c0e7b01f1022
    `lockedin_until_date_derived` DATE NULL COMMENT 'Fineract source column lockedin_until_date_derived',
    -- column_id: da441dd2-886d-449c-8386-20ab20c2b0fa
    `total_deposits_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_deposits_derived',
    -- column_id: 6fe45303-e392-479b-8991-03b2a30f8a90
    `total_withdrawals_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_withdrawals_derived',
    -- column_id: b0410e64-7131-4407-9a02-5419c154d0fb
    `total_withdrawal_fees_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_withdrawal_fees_derived',
    -- column_id: d261990b-b933-46e9-b706-fe2d41937a6d
    `total_fees_charge_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_fees_charge_derived',
    -- column_id: bcc18634-fbd3-4948-811c-548c3e474210
    `total_penalty_charge_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_penalty_charge_derived',
    -- column_id: 47b38196-9c18-48ac-ab1a-67579c7d277d
    `total_annual_fees_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_annual_fees_derived',
    -- column_id: 253b6b7a-3f18-40c9-a05d-e2d54d0d1da4
    `total_interest_earned_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_interest_earned_derived',
    -- column_id: 7bae18be-925e-45d6-afbb-b26cc0a60d07
    `total_interest_posted_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_interest_posted_derived',
    -- column_id: 8b94516d-d5fb-4967-927c-a6dbe571d0d9
    `total_overdraft_interest_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_overdraft_interest_derived',
    -- column_id: a6de894a-fb0b-47e3-a478-841a72642c0f
    `total_withhold_tax_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_withhold_tax_derived',
    -- column_id: 0325955d-e508-416a-b265-7b6d10b08f0a
    `account_balance_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column account_balance_derived',
    -- column_id: 233e96df-f888-4596-87ff-28de79a28fea
    `min_required_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_balance',
    -- column_id: 23ce8efd-e370-43cb-9b1c-fbe7fe5e79ce
    `enforce_min_required_balance` BOOLEAN NOT NULL COMMENT 'Fineract source column enforce_min_required_balance',
    -- column_id: a44c8043-bfab-4cad-9573-ae6c9ea64b90
    `min_balance_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_balance_for_interest_calculation',
    -- column_id: 94056afc-ab89-4670-b38f-808ff146d28d
    `start_interest_calculation_date` DATE NULL COMMENT 'Fineract source column start_interest_calculation_date',
    -- column_id: b1eb351e-0dd0-4146-a83d-e6c10bd28bd0
    `on_hold_funds_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column on_hold_funds_derived',
    -- column_id: ad55f55f-5840-4911-9003-23c83ec2ff2d
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: caacd761-c056-4cb7-b9e6-9a4880ecd279
    `withhold_tax` BOOLEAN NOT NULL COMMENT 'Fineract source column withhold_tax',
    -- column_id: a3f3855a-0a48-471f-987e-c85a48b7e5cf
    `tax_group_id` BIGINT NULL COMMENT 'Fineract source column tax_group_id',
    -- column_id: e9ce6151-8caa-4120-8699-db91b752ea47
    `last_interest_calculation_date` DATE NULL COMMENT 'Fineract source column last_interest_calculation_date',
    -- column_id: 9fdcf6f7-e801-4eb6-bc97-0c2ffa4c0d75
    `total_savings_amount_on_hold` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_savings_amount_on_hold',
    -- column_id: 4b498aad-0919-451a-a44d-3c782513a3b2
    `interest_posted_till_date` DATE NULL COMMENT 'Fineract source column interest_posted_till_date',
    -- column_id: bfa34f7b-f1c3-4408-bde5-c6d7f39890b8
    `reason_for_block` VARCHAR(256) NULL COMMENT 'Fineract source column reason_for_block',
    -- column_id: 9f281b18-1165-43be-82d7-8f7aa8059754
    `max_allowed_lien_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_allowed_lien_limit',
    -- column_id: 870c29b0-31b8-42de-b64a-542786eb5df2
    `is_lien_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_lien_allowed',
    -- column_id: 6b9d7ca0-959e-44e7-b8aa-dab3b660e139
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: c07e3299-f79b-4a4f-a382-5008d38f330a
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 7b4ea1ba-e7b5-4b96-9e94-b7f6e38d082b
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 61d5dd20-4e3a-48a3-a7f8-2f5b0fed2369
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: dedc4b62-c443-433f-86f4-c71abe700bd8
    `accrued_till_date` DATE NULL COMMENT 'Fineract source column accrued_till_date',
    -- column_id: 080259d0-702c-4d5a-9633-36b0ece99804
    `last_closed_business_date` DATE NULL COMMENT 'Fineract source column last_closed_business_date',
    -- column_id: 0737e892-d694-40f2-a4da-252c105c51b3
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
