-- ODS mirror of Apache Fineract m_charge (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_charge;
-- table_id: f8e35a28-7a20-4f4a-ad3d-0cd3901fb4e4
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_charge (
    -- column_id: 01246cb1-6f9b-4b01-aedc-ae1c00601512
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: da74f325-22d9-4aa6-beac-582be20186e7
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: db855290-aaf3-4abe-8d12-c90eecba49cd
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 842ae525-f46f-4c5d-96c8-622a70fc9739
    `charge_applies_to_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_applies_to_enum',
    -- column_id: e7a6169b-bb32-4d06-9a8a-33e7a5f7d525
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: 9c184f99-df0a-4c7f-97aa-8c9c847ac581
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: daf58ba2-48cd-4c0c-be52-018721b45182
    `charge_payment_mode_enum` SMALLINT NULL COMMENT 'Fineract source column charge_payment_mode_enum',
    -- column_id: ea0103c0-5072-41a0-a4fc-acec1a51e538
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 41c2a3a3-d8b8-44ac-aa64-fe379f95536c
    `fee_on_day` SMALLINT NULL COMMENT 'Fineract source column fee_on_day',
    -- column_id: 07418f69-3427-468c-8e14-f5eec49c2dbb
    `fee_interval` SMALLINT NULL COMMENT 'Fineract source column fee_interval',
    -- column_id: 09ff9917-e9bf-42bf-a729-0b55321af1d6
    `fee_on_month` SMALLINT NULL COMMENT 'Fineract source column fee_on_month',
    -- column_id: 14c41c2d-ebe6-4032-9b25-42070925a88c
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: 7e1cca52-eecb-4229-9027-096c01dec224
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 7af10400-5d96-4c96-bec9-e0e0fa2b6064
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: d1c105bd-8fcf-4989-a12c-b9e9ca360cc3
    `min_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_cap',
    -- column_id: a72866ae-9372-45a3-91a7-701468981ac4
    `max_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_cap',
    -- column_id: 0a4d5dd2-6e33-4bb9-b1c7-842a09a5c6f6
    `fee_frequency` SMALLINT NULL COMMENT 'Fineract source column fee_frequency',
    -- column_id: 6326d5ca-1266-48b7-9446-4b60ecdf13d9
    `is_free_withdrawal` BOOLEAN NOT NULL COMMENT 'Fineract source column is_free_withdrawal',
    -- column_id: 3a220b7b-c230-4dd7-ad93-a67a279d422c
    `free_withdrawal_charge_frequency` INT NULL COMMENT 'Fineract source column free_withdrawal_charge_frequency',
    -- column_id: 8b56fea3-8e1f-4278-91a0-2dbeae4def4f
    `restart_frequency` INT NULL COMMENT 'Fineract source column restart_frequency',
    -- column_id: d10c71af-0c30-4502-b355-c4f909feba76
    `restart_frequency_enum` INT NULL COMMENT 'Fineract source column restart_frequency_enum',
    -- column_id: 6c5adeb1-ea24-4ca6-8404-0fcecdde95e7
    `is_payment_type` BOOLEAN NULL COMMENT 'Fineract source column is_payment_type',
    -- column_id: 94e4ed85-3257-436c-830f-34be168769cd
    `payment_type_id` INT NULL COMMENT 'Fineract source column payment_type_id',
    -- column_id: bae19fe6-4249-4e0c-9925-e4fc124b0f4e
    `income_or_liability_account_id` BIGINT NULL COMMENT 'Fineract source column income_or_liability_account_id',
    -- column_id: 2bcb63a9-008e-4067-ad3f-9c5ff4030204
    `tax_group_id` BIGINT NULL COMMENT 'Fineract source column tax_group_id',
    -- column_id: 2e123e81-0bee-4c66-aa5d-6d3dd47a8af9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
