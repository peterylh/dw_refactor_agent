-- DWD generated from m_savings_account_charge
DROP TABLE IF EXISTS retail_banking_dm.dwd_deposit_charge;
-- table_id: c428c836-9f24-4fa0-b866-8521e6eb5715
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_deposit_charge (
    -- column_id: 43d15dc1-9aa9-4c1a-abf7-6232fb189881
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6352dc05-5c18-4c1f-9c2e-c06af7135133
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: bc6e891c-0a06-4dfc-b416-6664a208b092
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 06ce38e7-39f9-493a-9c2d-4a94fbf8692c
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: d25e5da0-d4fd-4985-adff-f87fd5e36d54
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: 0625ef5c-b079-41f9-8333-b7dbaa16a726
    `charge_due_date` DATE NULL COMMENT 'Fineract source column charge_due_date',
    -- column_id: 70afaf13-0d0c-4d4b-b4b7-252434f5b282
    `fee_on_month` SMALLINT NULL COMMENT 'Fineract source column fee_on_month',
    -- column_id: fdc6c50f-7ec3-4777-91b7-683fb7b58e93
    `fee_on_day` SMALLINT NULL COMMENT 'Fineract source column fee_on_day',
    -- column_id: 086e367d-f070-4505-83ad-656703265b90
    `fee_interval` SMALLINT NULL COMMENT 'Fineract source column fee_interval',
    -- column_id: 85d97cbd-9af4-4718-971b-7a2ea6842453
    `free_withdrawal_count` INT NULL COMMENT 'Fineract source column free_withdrawal_count',
    -- column_id: 620a36cf-dd75-49c0-a0a8-b8131c9b8a01
    `charge_reset_date` DATE NULL COMMENT 'Fineract source column charge_reset_date',
    -- column_id: 6a964dd6-e9e1-4692-9cd1-331622b886ea
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: 9d9de83b-df84-4e5b-b493-38c9ece03edc
    `calculation_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_percentage',
    -- column_id: 86581b0c-c67f-4fd9-8f9c-06522022737c
    `calculation_on_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_on_amount',
    -- column_id: fc6e6555-da03-4763-a211-33c064a8a07d
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 43287559-893b-4da1-bbae-39443f2ccea5
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: bdc0d3c6-ee8c-4108-9074-7613ce75fd13
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: ee23e166-00a8-4670-b764-4611eacbfd0a
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: 7134e2f3-3af0-47e4-98aa-34e5cc432ce2
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: e626f90e-af4b-4833-82dc-30271e4da488
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: b4e605ef-b5a1-46e3-b593-2a55ad537cf9
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: 8726592e-c82b-4967-89c8-93e760c98a2b
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 77cf8252-06e8-4d14-81ea-aed0b72b7613
    `inactivated_on_date` DATE NULL COMMENT 'Fineract source column inactivated_on_date',
    -- column_id: 41e8c0c3-c986-48a9-ab86-a2d2a8206bea
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: c6e0f0a1-24b2-4c3f-aab6-3f00e9b2f5e9
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 5ea47783-e569-4339-9850-09533a19120d
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 5d9dc7f9-ca41-4c4a-bc5c-7c2f3d5a2e3b
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: d2c4a543-8448-4078-8db4-8b0f139cb469
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 1247f5b6-7372-4820-8ac9-2be385932038
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
