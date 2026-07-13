-- DIM generated from m_savings_product
DROP TABLE IF EXISTS retail_banking_dm.dim_deposit_product;
-- table_id: 5fb73fba-12a5-43ba-a0e5-9db47dbd921f
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_deposit_product (
    -- column_id: b218a818-bfd8-4dc1-8780-c876114d88b3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ed0e2f79-f791-4513-89fe-131a98137956
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: ecef9552-24e9-4260-857b-22903bbf32b2
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: 728e0718-142a-456d-88a8-7dc4d9e1323a
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 3d5fb5ae-e027-4987-a756-10d06318f2cf
    `deposit_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column deposit_type_enum',
    -- column_id: 8ede481e-84f0-47e6-850a-2d43c1f770c4
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: f3a7d461-f923-4eaa-a829-c37716539909
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 200e0749-f4e8-4c5f-9aa7-fe278d78228a
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 8f48491d-d366-4f0c-8b55-3e6f4cfe628a
    `nominal_annual_interest_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column nominal_annual_interest_rate',
    -- column_id: 4f65192b-a2e6-4598-b618-d2eb2262b8ad
    `interest_compounding_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_compounding_period_enum',
    -- column_id: 291fe714-e700-4fa8-b0d9-6ba88a709716
    `interest_posting_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_posting_period_enum',
    -- column_id: ac6bf96c-bbe0-40c7-a934-9a4cfbbb34f6
    `interest_calculation_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_type_enum',
    -- column_id: e4dbd7bc-e3bf-4d4d-a0fb-d09399dd12df
    `interest_calculation_days_in_year_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_days_in_year_type_enum',
    -- column_id: ce027548-2125-48a2-87b1-a57b0741069e
    `min_required_opening_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_opening_balance',
    -- column_id: 6ba02fa4-9206-42bf-a681-cf58e90c7045
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: 62388e4c-b68f-4e53-aa44-6f70cb93ce97
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: 654f5919-5568-47d4-8d38-f2661bed9136
    `accounting_type` SMALLINT NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: e8d03ff2-db4e-4e93-86d6-e155c16c27b2
    `withdrawal_fee_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column withdrawal_fee_amount',
    -- column_id: 2ac1e192-1130-4382-9641-db26233369c2
    `withdrawal_fee_type_enum` SMALLINT NULL COMMENT 'Fineract source column withdrawal_fee_type_enum',
    -- column_id: 1d8cb1fa-eb81-4a1e-a848-f9c5b36250c5
    `withdrawal_fee_for_transfer` BOOLEAN NULL COMMENT 'Fineract source column withdrawal_fee_for_transfer',
    -- column_id: 8aa19534-17f4-4891-af87-7564e1ec4fa3
    `allow_overdraft` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_overdraft',
    -- column_id: 61421362-6bb8-41bb-b08f-37b9de92f3bd
    `overdraft_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column overdraft_limit',
    -- column_id: bfee2ffc-7725-43cb-b518-3241c46dba26
    `nominal_annual_interest_rate_overdraft` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_annual_interest_rate_overdraft',
    -- column_id: 920378c3-401a-4e1b-bc1a-31ab436a5898
    `min_overdraft_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_overdraft_for_interest_calculation',
    -- column_id: 9333a3a4-e102-4334-9c3e-c921df477934
    `min_required_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_balance',
    -- column_id: 738552a7-12cb-4076-8e69-d959d4cca5b6
    `enforce_min_required_balance` BOOLEAN NOT NULL COMMENT 'Fineract source column enforce_min_required_balance',
    -- column_id: e1f8d70a-2678-43fd-b3c6-37a58a9afe4c
    `min_balance_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_balance_for_interest_calculation',
    -- column_id: 16f515b8-61af-4481-86d8-18828fed932c
    `withhold_tax` BOOLEAN NOT NULL COMMENT 'Fineract source column withhold_tax',
    -- column_id: 3b1b8f9b-b5fe-49ce-9490-9782bef006b7
    `tax_group_id` BIGINT NULL COMMENT 'Fineract source column tax_group_id',
    -- column_id: abe9c415-8989-457e-950b-38676db37e4f
    `is_dormancy_tracking_active` BOOLEAN NULL COMMENT 'Fineract source column is_dormancy_tracking_active',
    -- column_id: d2d56bce-0ace-4f54-9193-f39605ed4d41
    `days_to_inactive` INT NULL COMMENT 'Fineract source column days_to_inactive',
    -- column_id: bed12768-9326-4dbc-a5d6-2d942a8d1bba
    `days_to_dormancy` INT NULL COMMENT 'Fineract source column days_to_dormancy',
    -- column_id: 98563c5a-a615-4e32-a1d4-b41989f2e9a9
    `days_to_escheat` INT NULL COMMENT 'Fineract source column days_to_escheat',
    -- column_id: 816731e7-9a73-4e30-b1ae-121532887038
    `max_allowed_lien_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_allowed_lien_limit',
    -- column_id: 01bcbd2c-6ff5-405b-b5e7-ca8b098e23a3
    `is_lien_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_lien_allowed',
    -- column_id: c764657c-f412-402c-ac79-6d4cf708185b
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
