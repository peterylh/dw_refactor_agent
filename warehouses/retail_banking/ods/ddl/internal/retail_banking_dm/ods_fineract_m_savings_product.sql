-- ODS mirror of Apache Fineract m_savings_product (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_product;
-- table_id: a2c986da-888a-423b-871a-a276ed70488b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_product (
    -- column_id: de3999e8-ca58-478c-8f5a-756d9c47e362
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e6e3c709-c785-4aa0-81dd-b7eb4fbfde64
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: dd691d9e-f724-420d-94b5-2cd1ff2e7c0f
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: c05d31e8-f9b2-4585-9682-7b4363ad5f44
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 0d2f50bf-4a02-49c9-94df-7deb60cd56e3
    `deposit_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column deposit_type_enum',
    -- column_id: 38cf7df5-1852-4c1e-93b5-80ba27ddd794
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 5a8f5674-135e-44d2-8c6f-bbf3334aebf6
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 848d2de7-409a-492d-8e72-7a74361ef8da
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: be9a2b8d-1f50-437b-81d1-9bcc1ec96ec1
    `nominal_annual_interest_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column nominal_annual_interest_rate',
    -- column_id: fbc566f6-f12f-46d0-ab32-56dc7d6b9297
    `interest_compounding_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_compounding_period_enum',
    -- column_id: 16791a3c-ba1a-4f5e-8378-ac0167d1474b
    `interest_posting_period_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_posting_period_enum',
    -- column_id: 04220aaa-c20a-4c53-ad64-35547604824d
    `interest_calculation_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_type_enum',
    -- column_id: 1e55754b-3b9b-4848-b957-59044449279a
    `interest_calculation_days_in_year_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column interest_calculation_days_in_year_type_enum',
    -- column_id: e47e09e8-dedd-480f-bbed-3d6682c5afb1
    `min_required_opening_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_opening_balance',
    -- column_id: 42085c86-2801-4d02-b60a-dced9cb02f06
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: 1717c49e-2fd9-482f-842e-ae594cea3bdd
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: 89ee76a1-d501-4643-bac9-eaebbc8c500c
    `accounting_type` SMALLINT NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: 2d20c97b-95b6-4733-b926-4f447c3b57a5
    `withdrawal_fee_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column withdrawal_fee_amount',
    -- column_id: 92ba1d9e-1839-4de9-bd6b-2c59928873bc
    `withdrawal_fee_type_enum` SMALLINT NULL COMMENT 'Fineract source column withdrawal_fee_type_enum',
    -- column_id: 5efc7585-7406-44bf-be3d-93935d67f982
    `withdrawal_fee_for_transfer` BOOLEAN NULL COMMENT 'Fineract source column withdrawal_fee_for_transfer',
    -- column_id: e57001a4-5015-4d6e-a836-f7ff406c0846
    `allow_overdraft` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_overdraft',
    -- column_id: 82ad62ca-c8ce-4f3b-9d69-aa4f761afa8b
    `overdraft_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column overdraft_limit',
    -- column_id: cd1692d9-d08b-4d96-a253-1c75745b6eae
    `nominal_annual_interest_rate_overdraft` DECIMAL(19,6) NULL COMMENT 'Fineract source column nominal_annual_interest_rate_overdraft',
    -- column_id: 3b112365-98ce-442e-b054-0bbb67acacbe
    `min_overdraft_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_overdraft_for_interest_calculation',
    -- column_id: 5ffb5a50-f613-4b74-998a-80677bd3cef3
    `min_required_balance` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_required_balance',
    -- column_id: c6277ab5-d01d-4485-bd4d-216f916a8e16
    `enforce_min_required_balance` BOOLEAN NOT NULL COMMENT 'Fineract source column enforce_min_required_balance',
    -- column_id: 253affec-1447-4533-9964-ce1239a90940
    `min_balance_for_interest_calculation` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_balance_for_interest_calculation',
    -- column_id: 9779beb0-e2cd-484a-a254-a931dac0abee
    `withhold_tax` BOOLEAN NOT NULL COMMENT 'Fineract source column withhold_tax',
    -- column_id: c5a2f9d2-fb61-49d5-a30e-b82bf55c8dd3
    `tax_group_id` BIGINT NULL COMMENT 'Fineract source column tax_group_id',
    -- column_id: 8202ea94-494e-43f9-9cd6-6206fc669cd6
    `is_dormancy_tracking_active` BOOLEAN NULL COMMENT 'Fineract source column is_dormancy_tracking_active',
    -- column_id: aa145385-71e8-4add-96a8-479bcabad6cf
    `days_to_inactive` INT NULL COMMENT 'Fineract source column days_to_inactive',
    -- column_id: 935c8907-14ce-4e7a-b990-24382f9d81fc
    `days_to_dormancy` INT NULL COMMENT 'Fineract source column days_to_dormancy',
    -- column_id: 56365205-60e9-4602-b298-720952f5312e
    `days_to_escheat` INT NULL COMMENT 'Fineract source column days_to_escheat',
    -- column_id: 45775624-2304-4882-9ce2-aea9a9b2f2f7
    `max_allowed_lien_limit` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_allowed_lien_limit',
    -- column_id: a3cd853f-8008-4318-9f01-04e1d77bcd4a
    `is_lien_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_lien_allowed',
    -- column_id: 937caca9-851f-4e07-a461-f36d329dbd4b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
