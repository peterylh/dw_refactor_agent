-- DIM generated from m_charge
DROP TABLE IF EXISTS retail_banking_dm.dim_charge_definition;
-- table_id: d9fc077d-1e26-4402-8492-c3da9e5f80e2
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_charge_definition (
    -- column_id: bbd48628-b8b4-4303-a994-c58c04a0f707
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 76476fba-bbfd-4e8e-9f77-c7506d3d9ae6
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 7e4483d9-86d1-4223-bd32-1037806c058c
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 40acf7c4-c05a-4850-a40f-63c333aacef9
    `charge_applies_to_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_applies_to_enum',
    -- column_id: 54a6c144-5472-4f7e-b1b0-b4512cddbcae
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: 7c9ce067-7f27-4933-83ba-9dbe3518fc4a
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: 2e8d0835-b9e9-4aad-95de-e235e0436ff3
    `charge_payment_mode_enum` SMALLINT NULL COMMENT 'Fineract source column charge_payment_mode_enum',
    -- column_id: a28eb5c6-2e02-4e05-a498-19fa023ba6f7
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 19ba3043-13f5-4c62-9cff-46c822f87899
    `fee_on_day` SMALLINT NULL COMMENT 'Fineract source column fee_on_day',
    -- column_id: 032619e2-716e-49d9-a2b2-1e56b4e6fe80
    `fee_interval` SMALLINT NULL COMMENT 'Fineract source column fee_interval',
    -- column_id: a3945462-69dc-4eff-925d-6f460beedc08
    `fee_on_month` SMALLINT NULL COMMENT 'Fineract source column fee_on_month',
    -- column_id: 05846258-4e39-4c54-bf3c-900c3ba21aa1
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: b86bf45b-e007-4087-b305-3e9a19d226d2
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: e029b6a4-4568-4667-b532-024b7bfb9e4f
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 19f70517-c773-4170-8370-1be1d19ec0aa
    `min_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_cap',
    -- column_id: 160c084c-126f-4f5d-a8cd-7732dc4a3af4
    `max_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_cap',
    -- column_id: 9bc3fd47-5093-4f02-977e-9d51f822abfc
    `fee_frequency` SMALLINT NULL COMMENT 'Fineract source column fee_frequency',
    -- column_id: c9bb643d-5a7c-4017-92bc-b9f03e5b453a
    `is_free_withdrawal` BOOLEAN NOT NULL COMMENT 'Fineract source column is_free_withdrawal',
    -- column_id: a85eff4f-8f02-4468-ac0b-9276a57473a7
    `free_withdrawal_charge_frequency` INT NULL COMMENT 'Fineract source column free_withdrawal_charge_frequency',
    -- column_id: ee18b8ab-9e91-4465-a967-546200c076eb
    `restart_frequency` INT NULL COMMENT 'Fineract source column restart_frequency',
    -- column_id: f9983cd8-e255-4440-9ea3-026e0f57ff78
    `restart_frequency_enum` INT NULL COMMENT 'Fineract source column restart_frequency_enum',
    -- column_id: 1908ffba-27b4-4fcf-b7e8-99fee6f7647b
    `is_payment_type` BOOLEAN NULL COMMENT 'Fineract source column is_payment_type',
    -- column_id: 0ecb3e13-dc2a-464c-860a-03431109541b
    `payment_type_id` INT NULL COMMENT 'Fineract source column payment_type_id',
    -- column_id: d5c2db01-7fe0-4ae0-9146-264667a47489
    `income_or_liability_account_id` BIGINT NULL COMMENT 'Fineract source column income_or_liability_account_id',
    -- column_id: 25b670d0-a386-44ef-acd0-90e7a79b9d50
    `tax_group_id` BIGINT NULL COMMENT 'Fineract source column tax_group_id',
    -- column_id: 6a38b0da-1724-486c-addb-853a026883b3
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
